import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user
from api.auth.models import User
from app.services.speaking_service import (
    get_all_prompt_sets_summary,
    get_prompt_set_by_id,
    get_random_prompt_set,
    get_adaptive_prompt_set,
    get_session_structure
)
from app.services.asr_service import transcribe_audio_bytes
from app.services.tts_service import examiner_speak
from app.services.speaking_evaluator_service import evaluate_speaking_attempt
from app.services.memory_service import (
    get_relevant_memories,
    save_speaking_attempt
)
from app.services.practice_service import mark_content_seen
from app.services.coach_service import coach_speaking_submission
from app.utils.logger import get_logger

logger = get_logger("api.routes.speaking")

router = APIRouter(prefix="/speaking", tags=["speaking"])


@router.get("/prompts")
async def get_prompts(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Returns all speaking prompt set summaries."""
    summaries = get_all_prompt_sets_summary()
    if difficulty:
        summaries = [
            p for p in summaries
            if p["difficulty"].lower() == difficulty.lower()
        ]
    return {"prompts": summaries}


@router.get("/prompt/random")
async def get_random_prompt(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Returns a speaking prompt set adapted to the learner's current band.
    Difficulty param overrides adaptive selection if provided.
    """
    try:
        if difficulty:
            prompt = get_random_prompt_set(difficulty=difficulty)
        elif current_user.learner_id:
            prompt = get_adaptive_prompt_set(current_user.learner_id)
        else:
            prompt = get_random_prompt_set()
        return {"prompt": get_session_structure(prompt)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/prompt/{prompt_set_id}")
async def get_prompt(
    prompt_set_id: str,
    current_user: User = Depends(get_current_user)
):
    """Returns a specific speaking prompt set by ID."""
    prompt = get_prompt_set_by_id(prompt_set_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt set not found")
    return {"prompt": get_session_structure(prompt)}


@router.get("/memories")
async def get_speaking_memories(
    current_user: User = Depends(get_current_user)
):
    """Returns active speaking memories."""
    if not current_user.learner_id:
        return {"memories": []}
    memories = get_relevant_memories(
        current_user.learner_id,
        section="Speaking",
        limit=3
    )
    return {"memories": memories}


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Transcribes uploaded audio using qwen3-asr-flash."""
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        filename = audio.filename or "recording.wav"
        ext = filename.rsplit('.', 1)[-1].lower()
        if ext not in ['wav', 'mp3', 'm4a', 'webm', 'ogg']:
            ext = 'wav'

        result = transcribe_audio_bytes(audio_bytes, audio_format=ext)
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Transcription failed: {result['error']}"
            )

        return {
            "success": True,
            "text": result["text"],
            "language": result.get("language", "en")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Transcription error: {str(e)}"
        )


class EvaluateSpeakingRequest(BaseModel):
    prompt_set_id: str
    part1_responses: dict
    part2_response: str
    part3_responses: dict


@router.post("/evaluate")
async def evaluate_speaking(
    request: EvaluateSpeakingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Evaluates a complete 3-part speaking session.
    Returns feedback immediately.
    Coach agent runs in background.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    learner_id = current_user.learner_id
    prompt_set = get_prompt_set_by_id(request.prompt_set_id)
    if not prompt_set:
        raise HTTPException(status_code=404, detail="Prompt set not found")

    memories = get_relevant_memories(
        learner_id, section="Speaking", limit=3
    )

    try:
        results = evaluate_speaking_attempt(
            prompt_set=prompt_set,
            part1_responses=request.part1_responses,
            part2_response=request.part2_response,
            part3_responses=request.part3_responses,
            memories=memories
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )

    if not results["success"]:
        raise HTTPException(
            status_code=500,
            detail=results.get("error", "Evaluation failed")
        )

    # Track prompt as seen
    mark_content_seen(learner_id, "Speaking", request.prompt_set_id)

    background_tasks.add_task(
        _speaking_post_tasks,
        learner_id=learner_id,
        results=results
    )

    return {
        "success": True,
        "feedback_text": results["feedback_text"],
        "scores": results["scores"],
        "topic": results.get("topic", ""),
        "difficulty": results.get("difficulty", "")
    }


async def _speaking_post_tasks(learner_id: str, results: dict):
    """Coach agent evaluates Speaking submission in background."""
    # Save attempt first — always runs regardless of Coach outcome
    try:
        save_speaking_attempt(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        logger.warning(f"Speaking save failed: {e}")

    try:
        coach_result = coach_speaking_submission(
            learner_id=learner_id,
            attempt_result=results
        )
        if coach_result.get("rank_ups"):
            logger.info(
                f"Speaking rank-ups for {learner_id}: "
                f"{[r['skill_id'] for r in coach_result['rank_ups']]}"
            )
        logger.info(
            f"Speaking Coach complete: "
            f"{coach_result.get('memories_written', 0)} memories written, "
            f"{len(coach_result.get('rank_ups', []))} rank-ups"
        )
    except Exception as e:
        logger.error(f"Speaking Coach agent failed: {e}", exc_info=True)


class TTSRequest(BaseModel):
    text: str


@router.post("/tts")
async def generate_tts(
    request: TTSRequest,
    current_user: User = Depends(get_current_user)
):
    """Converts examiner feedback to speech using Cherry voice."""
    if not request.text:
        raise HTTPException(status_code=400, detail="No text provided")

    result = examiner_speak(request.text)

    if not result["success"] or not result.get("audio_bytes"):
        raise HTTPException(
            status_code=500,
            detail=f"TTS failed: {result.get('error', 'Unknown error')}"
        )

    return StreamingResponse(
        io.BytesIO(result["audio_bytes"]),
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=feedback.wav"}
    )
