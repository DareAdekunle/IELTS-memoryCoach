import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import io
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user
from api.auth.models import User
from app.services.listening_service import (
    get_all_tracks_summary,
    get_track_by_id,
    get_random_track,
    evaluate_listening_attempt
)
from app.services.tts_service import generate_listening_audio
from app.services.memory_service import (
    get_relevant_memories,
    save_listening_attempt,
    extract_listening_memories,
    update_memories
)
from app.utils.logger import get_logger

logger = get_logger("api.routes.listening")

router = APIRouter(prefix="/listening", tags=["listening"])


@router.get("/tracks")
async def get_tracks(
    difficulty: Optional[str] = None,
    part: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """Returns all listening track summaries."""
    tracks = get_all_tracks_summary()
    if difficulty:
        tracks = [t for t in tracks if t["difficulty"].lower() == difficulty.lower()]
    if part:
        tracks = [t for t in tracks if t["part"] == part]
    return {"tracks": tracks}


@router.get("/track/{track_id}")
async def get_track(
    track_id: str,
    current_user: User = Depends(get_current_user)
):
    """Returns a specific track with full questions."""
    track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return {"track": track}


@router.get("/memories")
async def get_listening_memories(
    current_user: User = Depends(get_current_user)
):
    """Returns active listening memories."""
    if not current_user.learner_id:
        return {"memories": []}
    memories = get_relevant_memories(
        current_user.learner_id,
        section="Listening",
        limit=3
    )
    return {"memories": memories}


@router.get("/audio/{track_id}")
async def get_track_audio(
    track_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Generates or retrieves TTS audio for a listening track.

    If OSS is configured:
        - First request: generates audio, uploads to OSS,
          redirects to signed OSS URL
        - Subsequent requests: redirects to signed OSS URL instantly
          (audio served from Alibaba Cloud OSS, not from ECS)

    If OSS is not configured:
        - Falls back to disk cache, streams bytes directly

    This approach means audio for Listening tracks is served
    from Alibaba Cloud OSS infrastructure after first generation,
    reducing ECS bandwidth and demonstrating OSS integration.
    """
    track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    result = generate_listening_audio(track)

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Audio generation failed: {result.get('error', 'Unknown error')}"
        )

    # If OSS URL available — redirect React to fetch directly from OSS
    # This is the key architectural benefit: audio served from OSS CDN
    if result.get("audio_url"):
        logger.info(
            f"Serving track {track_id} from OSS "
            f"(storage={result.get('storage')}, "
            f"from_cache={result.get('from_cache')})"
        )
        return RedirectResponse(url=result["audio_url"])

    # Fallback: stream bytes from disk cache
    if result.get("audio_bytes"):
        logger.info(
            f"Streaming track {track_id} from disk cache"
        )
        return StreamingResponse(
            io.BytesIO(result["audio_bytes"]),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=track_{track_id}.wav"
            }
        )

    raise HTTPException(status_code=500, detail="No audio available")


class SubmitListeningRequest(BaseModel):
    track_id: str
    answers: dict


@router.post("/submit")
async def submit_listening(
    request: SubmitListeningRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Submits listening answers for evaluation."""
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    learner_id = current_user.learner_id
    track = get_track_by_id(request.track_id)

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    try:
        results = evaluate_listening_attempt(
            track=track,
            learner_answers=request.answers
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )

    try:
        save_listening_attempt(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        logger.warning(f"Could not save listening attempt: {e}")

    background_tasks.add_task(
        _listening_post_tasks,
        learner_id=learner_id,
        results=results
    )

    return {
        "success": True,
        "track_title": results["track_title"],
        "part": results["part"],
        "total_score": results["total_score"],
        "max_score": results["max_score"],
        "percentage": results["percentage"],
        "skill_accuracy": results["skill_accuracy"],
        "question_results": results["question_results"]
    }


async def _listening_post_tasks(learner_id: str, results: dict):
    """Background memory tasks after listening submission."""
    try:
        extract_listening_memories(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        logger.warning(f"Listening memory extraction failed: {e}")

    try:
        skill_accuracy = results.get("skill_accuracy", {})
        update_memories(
            learner_id=learner_id,
            section="Listening",
            score_result={
                "scores": {
                    skill: acc / 20
                    for skill, acc in skill_accuracy.items()
                },
                "strengths": [
                    f"{skill}: {acc}%"
                    for skill, acc in skill_accuracy.items()
                    if acc >= 80
                ],
                "weaknesses": [
                    f"{skill}: {acc}%"
                    for skill, acc in skill_accuracy.items()
                    if acc < 60
                ],
                "overall_feedback": (
                    f"Score: {results['total_score']} / "
                    f"{results['max_score']} ({results['percentage']}%)"
                )
            }
        )
    except Exception as e:
        logger.warning(f"Listening memory update failed: {e}")
