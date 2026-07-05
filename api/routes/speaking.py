import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import io

from api.dependencies import get_current_user
from api.auth.models import User
from app.services.speaking_service import (
    get_all_prompt_sets_summary,
    get_prompt_set_by_id,
    get_random_prompt_set,
    get_session_structure
)
from app.services.asr_service import transcribe_audio_bytes
from app.services.tts_service import examiner_speak
from app.services.speaking_evaluator_service import evaluate_speaking_attempt
from app.services.memory_service import (
    get_relevant_memories,
    save_speaking_attempt,
    extract_speaking_memories,
    update_memories
)

router = APIRouter(prefix="/speaking", tags=["speaking"])


# ─── Prompt sets ──────────────────────────────────────────────────────────────

@router.get("/prompts")
async def get_prompts(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Returns all speaking prompt set summaries for the selection screen."""
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
    """Returns a random speaking prompt set."""
    try:
        prompt = get_random_prompt_set(
            difficulty=difficulty if difficulty else None
        )
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
    """Returns active speaking memories for the memory panel."""
    if not current_user.learner_id:
        return {"memories": []}
    memories = get_relevant_memories(
        current_user.learner_id,
        section="Speaking",
        limit=3
    )
    return {"memories": memories}


# ─── ASR — transcribe audio ───────────────────────────────────────────────────

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Transcribes an uploaded audio file using Qwen ASR.
    Called after each question response is recorded or uploaded.
    Returns the transcription text immediately.
    """
    try:
        audio_bytes = await audio.read()

        if not audio_bytes:
            raise HTTPException(
                status_code=400,
                detail="Empty audio file received"
            )

        # Detect format from filename
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


# ─── Evaluate full speaking session ───────────────────────────────────────────

class EvaluateSpeakingRequest(BaseModel):
    prompt_set_id: str
    part1_responses: dict   # {"0": "text", "1": "text", ...}
    part2_response: str
    part3_responses: dict   # {"0": "text", "1": "text", ...}


@router.post("/evaluate")
async def evaluate_speaking(
    request: EvaluateSpeakingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Evaluates a complete 3-part speaking session.
    Returns written feedback and band scores immediately.
    TTS audio is generated separately via /speaking/tts endpoint
    to avoid timeout issues with large audio files.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    learner_id = current_user.learner_id

    prompt_set = get_prompt_set_by_id(request.prompt_set_id)
    if not prompt_set:
        raise HTTPException(
            status_code=404,
            detail="Prompt set not found"
        )

    memories = get_relevant_memories(
        learner_id, section="Speaking", limit=5
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

    # Save attempt + extract memories in background
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
    """Background tasks after speaking evaluation."""
    try:
        save_speaking_attempt(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        print(f"Speaking save failed: {e}")

    try:
        extract_speaking_memories(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        print(f"Speaking memory extraction failed: {e}")

    try:
        scores = results.get("scores", {})
        update_memories(
            learner_id=learner_id,
            section="Speaking",
            score_result={
                "scores": {
                    "fluency_coherence": scores.get("fluency_coherence", 0),
                    "lexical_resource": scores.get("lexical_resource", 0),
                    "grammatical_range": scores.get("grammatical_range", 0),
                    "pronunciation_clarity": scores.get(
                        "pronunciation_clarity", 0
                    ),
                },
                "strengths": scores.get("strengths", []),
                "weaknesses": scores.get("weaknesses", []),
                "overall_feedback": results.get("feedback_text", "")
            }
        )
    except Exception as e:
        print(f"Speaking memory update failed: {e}")


# ─── TTS — generate spoken feedback ───────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str


@router.post("/tts")
async def generate_tts(
    request: TTSRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Converts examiner feedback text to speech using Qwen TTS.
    Returns the audio as a WAV file stream.
    Called separately after /evaluate so we don't block the
    feedback display while waiting for TTS generation.
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="No text provided")

    result = examiner_speak(request.text)

    if not result["success"] or not result["audio_bytes"]:
        raise HTTPException(
            status_code=500,
            detail=f"TTS generation failed: {result.get('error', 'Unknown error')}"
        )

    return StreamingResponse(
        io.BytesIO(result["audio_bytes"]),
        media_type="audio/wav",
        headers={
            "Content-Disposition": "attachment; filename=feedback.wav"
        }
    )
