import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user, get_db
from api.auth.models import User
from app.services.practice_service import (
    get_adaptive_writing_prompt,
    get_random_writing_prompt
)
from app.services.scoring_service import (
    evaluate_writing,
    evaluate_writing_from_image
)
from app.services.memory_service import (
    save_attempt,
    get_relevant_memories
)
from app.services.coach_service import coach_writing_submission
from app.utils.logger import get_logger

logger = get_logger("api.routes.writing")

router = APIRouter(prefix="/writing", tags=["writing"])


class SubmitEssayRequest(BaseModel):
    prompt: str
    task_type: str
    essay: str
    prompt_id: Optional[str] = None


class PromptResponse(BaseModel):
    prompt_id: str
    prompt: str
    task_type: str
    difficulty: str
    target_skills: list


def compress_memories_for_prompt(memories: list, limit: int = 3) -> str:
    if not memories:
        return "No previous memories for this learner yet."
    sorted_mems = sorted(
        memories[:limit],
        key=lambda m: (m['memory_type'] != 'weakness', -m.get('confidence', 0))
    )
    lines = []
    for m in sorted_mems:
        icon = "⚠️" if m['memory_type'] == 'weakness' else "✅"
        text = m['memory_text'][:80] + "..." if len(m['memory_text']) > 80 else m['memory_text']
        lines.append(f"{icon} {m['skill']}: {text}")
    return "\n".join(lines)


@router.get("/prompt", response_model=PromptResponse)
async def get_prompt(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Returns a writing prompt adapted to the learner's current band level.
    If no band data exists yet, returns an intermediate prompt.
    The difficulty query param can override adaptive selection.
    """
    try:
        if difficulty:
            # Manual override
            from app.services.practice_service import _get_prompt_by_difficulty
            prompt = _get_prompt_by_difficulty(difficulty)
        elif current_user.learner_id:
            # Adaptive selection based on learner's band
            prompt = get_adaptive_writing_prompt(current_user.learner_id)
        else:
            prompt = get_random_writing_prompt()

        return PromptResponse(
            prompt_id=prompt["prompt_id"],
            prompt=prompt["prompt"],
            task_type=prompt["task_type"],
            difficulty=prompt["difficulty"],
            target_skills=prompt["target_skills"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories")
async def get_writing_memories(
    current_user: User = Depends(get_current_user)
):
    if not current_user.learner_id:
        return {"memories": []}
    memories = get_relevant_memories(
        current_user.learner_id, section="Writing", limit=3
    )
    return {"memories": memories}


@router.post("/submit")
async def submit_essay(
    request: SubmitEssayRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Standard (non-streaming) essay submission."""
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")

    learner_id = current_user.learner_id
    memories = get_relevant_memories(learner_id, section="Writing", limit=3)

    try:
        result = evaluate_writing(
            prompt=request.prompt,
            essay=request.essay,
            memories=memories
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Essay evaluation failed: {str(e)}")

    try:
        save_attempt(
            learner_id=learner_id,
            section="Writing",
            task_type=request.task_type,
            prompt=request.prompt,
            learner_response=request.essay,
            score_json=result,
            feedback=result.get("overall_feedback", "")
        )
    except Exception as e:
        logger.warning(f"Could not save attempt: {e}")

    background_tasks.add_task(
        _writing_post_tasks,
        learner_id=learner_id,
        prompt=request.prompt,
        essay=request.essay,
        result=result
    )

    return {
        "success": True,
        "overall_feedback": result.get("overall_feedback", ""),
        "scores": result.get("scores", {}),
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "memory_references": result.get("memory_references", []),
        "recommended_next_step": result.get("recommended_next_step", "")
    }


@router.post("/submit/image")
async def submit_essay_image(
    background_tasks: BackgroundTasks,
    prompt: str = "",
    task_type: str = "Academic Discussion",
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Handwritten essay submission via image upload.

    Step 1: qwen-vl-plus extracts the handwritten text from the image
    Step 2: Extracted text is evaluated using the standard Writing pipeline

    Supports JPEG, PNG and WebP images.
    The essay must be clearly legible — poor image quality will reduce
    extraction accuracy.
    """
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")

    # Validate file type
    filename = image.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower()
    media_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp"
    }
    if ext not in media_type_map:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Please upload JPEG, PNG or WebP."
        )
    media_type = media_type_map[ext]

    # Read image bytes
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    learner_id = current_user.learner_id
    memories = get_relevant_memories(learner_id, section="Writing", limit=3)

    try:
        result = evaluate_writing_from_image(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=prompt,
            memories=memories
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    extracted_text = result.pop("extracted_text", "")
    extraction_confidence = result.pop("extraction_confidence", "medium")
    extraction_notes = result.pop("extraction_notes", "")
    word_count = result.pop("word_count", 0)

    try:
        save_attempt(
            learner_id=learner_id,
            section="Writing",
            task_type=task_type,
            prompt=prompt,
            learner_response=extracted_text,
            score_json=result,
            feedback=result.get("overall_feedback", "")
        )
    except Exception as e:
        logger.warning(f"Could not save image attempt: {e}")

    background_tasks.add_task(
        _writing_post_tasks,
        learner_id=learner_id,
        prompt=prompt,
        essay=extracted_text,
        result=result
    )

    return {
        "success": True,
        "overall_feedback": result.get("overall_feedback", ""),
        "scores": result.get("scores", {}),
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "memory_references": result.get("memory_references", []),
        "recommended_next_step": result.get("recommended_next_step", ""),
        "extracted_text": extracted_text,
        "extraction_confidence": extraction_confidence,
        "extraction_notes": extraction_notes,
        "word_count": word_count
    }


@router.post("/submit/stream")
async def submit_essay_stream(
    request: SubmitEssayRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Streaming essay submission via SSE."""
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")

    learner_id = current_user.learner_id
    memories = get_relevant_memories(learner_id, section="Writing", limit=3)
    memory_context = compress_memories_for_prompt(memories)

    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "app", "prompts", "writing_evaluator_prompt.txt"
    )
    with open(prompt_path) as f:
        template = f.read()

    full_prompt = template.format(
        prompt=request.prompt,
        essay=request.essay,
        memories=memory_context,
        rubric="Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy"
    )

    from app.services.qwen_service import client, QWEN_MODEL

    async def generate():
        collected = []
        result = {}
        try:
            stream = client.chat.completions.create(
                model=QWEN_MODEL,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3,
                stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    collected.append(delta)
                    yield f"data: {json.dumps({'token': delta})}\n\n"

            full_response = "".join(collected)

            from app.utils.json_utils import safe_parse_json, extract_json_from_text
            try:
                result = safe_parse_json(full_response)
            except Exception:
                try:
                    result = extract_json_from_text(full_response)
                except Exception:
                    result = {
                        "overall_feedback": full_response,
                        "scores": {},
                        "strengths": [],
                        "weaknesses": [],
                        "recommended_next_step": ""
                    }

            try:
                save_attempt(
                    learner_id=learner_id,
                    section="Writing",
                    task_type=request.task_type,
                    prompt=request.prompt,
                    learner_response=request.essay,
                    score_json=result,
                    feedback=result.get("overall_feedback", "")
                )
            except Exception as e:
                logger.warning(f"Save attempt failed: {e}")

            yield f"data: {json.dumps({'done': True, 'result': result})}\n\n"

            background_tasks.add_task(
                _writing_post_tasks,
                learner_id=learner_id,
                prompt=request.prompt,
                essay=request.essay,
                result=result
            )

        except Exception as e:
            logger.error(f"Streaming evaluation failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/attempts")
async def get_writing_attempts(current_user: User = Depends(get_current_user)):
    if not current_user.learner_id:
        return {"attempts": []}
    from app.services.memory_service import get_attempts
    attempts = get_attempts(current_user.learner_id, section="Writing")
    return {"attempts": attempts}


async def _writing_post_tasks(
    learner_id: str, prompt: str, essay: str, result: dict
):
    """Coach agent evaluates Writing submission in background."""
    try:
        coach_result = coach_writing_submission(
            learner_id=learner_id,
            prompt=prompt,
            essay=essay,
            score_result=result,
            feedback=result.get("overall_feedback", "")
        )
        if coach_result.get("rank_ups"):
            logger.info(
                f"Writing rank-ups for {learner_id}: "
                f"{[r['skill_id'] for r in coach_result['rank_ups']]}"
            )
        logger.info(
            f"Writing Coach complete: "
            f"{coach_result.get('memories_written', 0)} memories written, "
            f"{len(coach_result.get('rank_ups', []))} rank-ups"
        )
    except Exception as e:
        logger.error(f"Writing Coach agent failed: {e}", exc_info=True)
