import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user, get_db
from api.auth.models import User
from app.services.practice_service import get_random_writing_prompt
from app.services.scoring_service import evaluate_writing
from app.services.memory_service import (
    save_attempt,
    extract_and_save_memories,
    get_relevant_memories,
    update_memories,
    apply_skill_classifications_batch
)
from app.services.skill_classifier_service import classify_writing_skills
from app.utils.logger import get_logger

logger = get_logger("api.routes.writing")

router = APIRouter(prefix="/writing", tags=["writing"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def compress_memories_for_prompt(memories: list, limit: int = 3) -> str:
    """
    Compresses memories to minimal tokens for prompt injection.
    Sends skill + type + first 80 chars only.
    Reduces prompt token count by ~60% for learners with many memories.
    Prioritises weaknesses over strengths — more actionable for the evaluator.
    """
    if not memories:
        return "No previous memories for this learner yet."

    sorted_mems = sorted(
        memories[:limit],
        key=lambda m: (m['memory_type'] != 'weakness', -m.get('confidence', 0))
    )

    lines = []
    for m in sorted_mems:
        icon = "⚠️" if m['memory_type'] == 'weakness' else "✅"
        text = m['memory_text'][:80] + "..." if len(
            m['memory_text']
        ) > 80 else m['memory_text']
        lines.append(f"{icon} {m['skill']}: {text}")

    return "\n".join(lines)


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/prompt", response_model=PromptResponse)
async def get_prompt(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Returns a random writing prompt."""
    try:
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
    """Returns the learner's active writing memories for the memory panel."""
    if not current_user.learner_id:
        return {"memories": []}

    memories = get_relevant_memories(
        current_user.learner_id,
        section="Writing",
        limit=3
    )
    return {"memories": memories}


@router.post("/submit")
async def submit_essay(
    request: SubmitEssayRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Standard (non-streaming) essay submission.
    Returns full feedback after evaluation completes (~15-20s).
    Use /submit/stream for streaming version with faster TTFT.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first before submitting"
        )

    learner_id = current_user.learner_id
    memories = get_relevant_memories(learner_id, section="Writing", limit=3)

    try:
        result = evaluate_writing(
            prompt=request.prompt,
            essay=request.essay,
            memories=memories
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Essay evaluation failed: {str(e)}"
        )

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
        _run_post_submission_tasks,
        learner_id=learner_id,
        prompt=request.prompt,
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


@router.post("/submit/stream")
async def submit_essay_stream(
    request: SubmitEssayRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Streaming essay submission via Server-Sent Events.
    Sends feedback tokens as they are generated — learner sees
    the first token in ~1-2 seconds instead of waiting 15-20s.

    SSE format:
      data: {"token": "..."} — individual token as generated
      data: {"done": true, "result": {...}} — full parsed result
      data: {"error": "..."} — on failure
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    learner_id = current_user.learner_id
    memories = get_relevant_memories(learner_id, section="Writing", limit=3)
    memory_context = compress_memories_for_prompt(memories)

    # Load evaluator prompt template
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "app", "prompts", "writing_evaluator_prompt.txt"
    )
    with open(prompt_path) as f:
        template = f.read()

    full_prompt = template.format(
        prompt=request.prompt,
        essay=request.essay,
        memories=memory_context
    )

    from app.services.qwen_service import client, QWEN_MODEL

    async def generate():
        collected = []
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

            # Parse the collected response
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

            # Save attempt
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

            # Signal completion with full parsed result
            yield f"data: {json.dumps({'done': True, 'result': result})}\n\n"

            # Run background tasks after response is fully sent
            background_tasks.add_task(
                _run_post_submission_tasks,
                learner_id=learner_id,
                prompt=request.prompt,
                result=result
            )

        except Exception as e:
            logger.error(f"Streaming evaluation failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/attempts")
async def get_writing_attempts(
    current_user: User = Depends(get_current_user)
):
    """Returns all writing attempts for the Progress Dashboard."""
    if not current_user.learner_id:
        return {"attempts": []}

    from app.services.memory_service import get_attempts
    attempts = get_attempts(current_user.learner_id, section="Writing")
    return {"attempts": attempts}


# ─── Background tasks ─────────────────────────────────────────────────────────

async def _run_post_submission_tasks(
    learner_id: str,
    prompt: str,
    result: dict
):
    """
    Runs after the essay response is sent.
    Updates memory and skill profiles in the background.
    Errors here are logged but never shown to the learner.
    """
    try:
        extract_and_save_memories(
            learner_id=learner_id,
            section="Writing",
            prompt=prompt,
            score_result=result
        )
    except Exception as e:
        logger.warning(f"Memory extraction failed (non-blocking): {e}")

    try:
        update_memories(
            learner_id=learner_id,
            section="Writing",
            score_result=result
        )
    except Exception as e:
        logger.warning(f"Memory update failed (non-blocking): {e}")

    try:
        classifications = classify_writing_skills(
            prompt=prompt,
            essay=result.get("essay_text", "")
        )
        apply_skill_classifications_batch(
            learner_id=learner_id,
            section="Writing",
            classifications=classifications
        )
    except Exception as e:
        logger.warning(f"Skill classification failed (non-blocking): {e}")
