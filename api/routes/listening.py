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
from app.services.listening_service import get_adaptive_track
from app.services.tts_service import generate_listening_audio
from app.services.memory_service import (
    get_relevant_memories,
    save_listening_attempt
)
from app.services.practice_service import mark_content_seen
from app.services.coach_service import coach_listening_submission
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


@router.get("/track/random")
async def get_random_listening_track(
    current_user: User = Depends(get_current_user)
):
    """
    Returns a listening track adapted to the learner's current band level.
    Avoids tracks already seen — cycles back only when all at the level
    have been completed.
    """
    try:
        if current_user.learner_id:
            track = get_adaptive_track(current_user.learner_id)
        else:
            track = get_random_track()
        return {"track": track}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    First request: generates, uploads to OSS, redirects to signed URL.
    Subsequent requests: redirects to OSS instantly (zero TTS cost).
    Fallback: streams from disk cache if OSS not configured.
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

    if result.get("audio_url"):
        logger.info(
            f"Serving track {track_id} from OSS "
            f"(storage={result.get('storage')}, "
            f"from_cache={result.get('from_cache')})"
        )
        # Proxy the OSS audio instead of redirecting.
        # Browsers cannot follow cross-origin 307 redirects when an
        # Authorization header is present — the auth header gets sent
        # to OSS which rejects it. Proxying through FastAPI avoids this.
        import requests as _requests
        oss_response = _requests.get(result["audio_url"], timeout=30, stream=True)
        if oss_response.status_code == 200:
            return StreamingResponse(
                oss_response.iter_content(chunk_size=8192),
                media_type="audio/wav",
                headers={"Content-Disposition": f"inline; filename=track_{track_id}.wav"}
            )
        # Fallback: redirect anyway (better than nothing)
        return RedirectResponse(url=result["audio_url"])

    if result.get("audio_bytes"):
        logger.info(f"Streaming track {track_id} from disk cache")
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
    """
    Submits listening answers for evaluation.
    Returns results immediately.
    Coach agent runs in background.
    """
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

    # Track track as seen
    mark_content_seen(learner_id, "Listening", request.track_id)

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
    """Coach agent evaluates Listening submission in background."""
    try:
        coach_result = coach_listening_submission(
            learner_id=learner_id,
            attempt_result=results
        )
        if coach_result.get("rank_ups"):
            logger.info(
                f"Listening rank-ups for {learner_id}: "
                f"{[r['skill_id'] for r in coach_result['rank_ups']]}"
            )
        logger.info(
            f"Listening Coach complete: "
            f"{coach_result.get('memories_written', 0)} memories written, "
            f"{len(coach_result.get('rank_ups', []))} rank-ups"
        )
    except Exception as e:
        logger.error(f"Listening Coach agent failed: {e}", exc_info=True)
