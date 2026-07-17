import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user
from api.auth.models import User
from app.services.reading_service import (
    get_random_passage,
    get_adaptive_passage,
    get_all_passages_summary,
    get_passage_by_id,
    evaluate_reading_attempt
)
from app.services.memory_service import (
    get_relevant_memories,
    save_reading_attempt
)
from app.services.practice_service import mark_content_seen
from app.services.coach_service import coach_reading_submission
from app.utils.logger import get_logger

logger = get_logger("api.routes.reading")

router = APIRouter(prefix="/reading", tags=["reading"])


class SubmitReadingRequest(BaseModel):
    passage_id: str
    answers: dict


@router.get("/passages")
async def get_passages(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Returns all reading passage summaries."""
    summaries = get_all_passages_summary()
    if difficulty:
        summaries = [
            p for p in summaries
            if p["difficulty"].lower() == difficulty.lower()
        ]
    return {"passages": summaries}


@router.get("/passage/random")
async def get_random_reading_passage(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Returns a reading passage adapted to the learner's current band.
    Difficulty param overrides adaptive selection if provided.
    """
    try:
        if difficulty:
            passage = get_random_passage(difficulty=difficulty)
        elif current_user.learner_id:
            passage = get_adaptive_passage(current_user.learner_id)
        else:
            passage = get_random_passage()
        return {"passage": passage}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/passage/{passage_id}")
async def get_passage(
    passage_id: str,
    current_user: User = Depends(get_current_user)
):
    """Returns a specific reading passage by ID."""
    passage = get_passage_by_id(passage_id)
    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")
    return {"passage": passage}


@router.get("/memories")
async def get_reading_memories(
    current_user: User = Depends(get_current_user)
):
    """Returns active reading memories for the memory panel."""
    if not current_user.learner_id:
        return {"memories": []}
    memories = get_relevant_memories(
        current_user.learner_id,
        section="Reading",
        limit=3
    )
    return {"memories": memories}


@router.post("/submit")
async def submit_reading(
    request: SubmitReadingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Submits reading answers for evaluation.
    Returns results immediately.
    Coach agent runs in background.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    learner_id = current_user.learner_id
    passage = get_passage_by_id(request.passage_id)
    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    try:
        results = evaluate_reading_attempt(
            passage=passage,
            learner_answers=request.answers
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )

    try:
        save_reading_attempt(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        logger.warning(f"Could not save reading attempt: {e}")

    # Track this passage as seen so adaptive selection avoids repeats
    mark_content_seen(learner_id, "Reading", request.passage_id)

    background_tasks.add_task(
        _reading_post_tasks,
        learner_id=learner_id,
        results=results
    )

    return {
        "success": True,
        "passage_title": results["passage_title"],
        "total_score": results["total_score"],
        "max_score": results["max_score"],
        "percentage": results["percentage"],
        "skill_accuracy": results["skill_accuracy"],
        "question_results": results["question_results"]
    }


async def _reading_post_tasks(learner_id: str, results: dict):
    """Coach agent evaluates Reading submission in background."""
    try:
        coach_result = coach_reading_submission(
            learner_id=learner_id,
            attempt_result=results
        )
        if coach_result.get("rank_ups"):
            logger.info(
                f"Reading rank-ups for {learner_id}: "
                f"{[r['skill_id'] for r in coach_result['rank_ups']]}"
            )
        logger.info(
            f"Reading Coach complete: "
            f"{coach_result.get('memories_written', 0)} memories written, "
            f"{len(coach_result.get('rank_ups', []))} rank-ups"
        )
    except Exception as e:
        logger.error(f"Reading Coach agent failed: {e}", exc_info=True)
