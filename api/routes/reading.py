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
    get_all_passages_summary,
    get_passage_by_id,
    evaluate_reading_attempt
)
from app.services.memory_service import (
    get_relevant_memories,
    save_reading_attempt,
    extract_reading_memories,
    update_memories
)

router = APIRouter(prefix="/reading", tags=["reading"])


class SubmitReadingRequest(BaseModel):
    passage_id: str
    answers: dict  # {"q1": "B", "q2": "True", "q3": "some text answer"}


@router.get("/passages")
async def get_passages(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Returns a summary list of all available reading passages.
    Used to populate the passage selection screen.
    """
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
    """Returns a random full reading passage with all questions."""
    try:
        passage = get_random_passage(difficulty=difficulty)
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
        limit=5
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
    Objective questions (MC, T/F/NG) checked instantly.
    Short answers evaluated by Qwen.
    Returns results immediately, memory tasks run in background.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    learner_id = current_user.learner_id

    # Get the passage
    passage = get_passage_by_id(request.passage_id)
    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    # Evaluate answers
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

    # Save attempt synchronously
    try:
        save_reading_attempt(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        print(f"Warning: Could not save reading attempt: {e}")

    # Memory tasks in background
    background_tasks.add_task(
        _run_reading_post_tasks,
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


async def _run_reading_post_tasks(learner_id: str, results: dict):
    """Background memory tasks for reading submissions."""
    try:
        extract_reading_memories(
            learner_id=learner_id,
            attempt_result=results
        )
    except Exception as e:
        print(f"Reading memory extraction failed: {e}")

    try:
        skill_accuracy = results.get("skill_accuracy", {})
        update_memories(
            learner_id=learner_id,
            section="Reading",
            score_result={
                "scores": {
                    skill: acc / 20
                    for skill, acc in skill_accuracy.items()
                },
                "strengths": [
                    f"{skill} accuracy: {acc}%"
                    for skill, acc in skill_accuracy.items()
                    if acc >= 80
                ],
                "weaknesses": [
                    f"{skill} accuracy: {acc}%"
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
        print(f"Reading memory update failed: {e}")
