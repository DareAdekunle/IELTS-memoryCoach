import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

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

router = APIRouter(prefix="/writing", tags=["writing"])


# ─── Request / Response schemas ───────────────────────────────────────────────

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


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/prompt", response_model=PromptResponse)
async def get_prompt(
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Returns a random writing prompt.
    Optionally filtered by difficulty: beginner, intermediate, advanced.
    The learner's linked learner_id is used to retrieve relevant memories
    so the frontend can show the memory panel.
    """
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
    """
    Returns the learner's active writing memories.
    Called by the Writing Coach page before the learner starts writing
    so the memory panel can be shown.
    """
    if not current_user.learner_id:
        return {"memories": []}

    memories = get_relevant_memories(
        current_user.learner_id,
        section="Writing",
        limit=5
    )
    return {"memories": memories}


@router.post("/submit")
async def submit_essay(
    request: SubmitEssayRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Submits an essay for evaluation.

    Steps:
    1. Score the essay with Qwen (rubric + memory context)
    2. Save the attempt
    3. Run memory extraction + skill classification in background
       (so the learner gets feedback immediately without waiting
       for the background tasks to complete)

    Returns scores and feedback immediately.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first before submitting"
        )

    learner_id = current_user.learner_id

    # Get existing memories to pass as context to the evaluator
    memories = get_relevant_memories(learner_id, section="Writing", limit=5)

    # Step 1: Score the essay
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

    # Step 2: Save the attempt synchronously (needed before background tasks)
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
        print(f"Warning: Could not save attempt: {e}")

    # Step 3: Memory extraction + skill ranking in background
    # Learner gets feedback immediately, these run after the response is sent
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


async def _run_post_submission_tasks(
    learner_id: str,
    prompt: str,
    result: dict
):
    """
    Background tasks that run after the essay response is sent.
    These update the learner's memory and skill profiles.
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
        print(f"Memory extraction failed (non-blocking): {e}")

    try:
        update_memories(
            learner_id=learner_id,
            section="Writing",
            score_result=result
        )
    except Exception as e:
        print(f"Memory update failed (non-blocking): {e}")

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
        print(f"Skill classification failed (non-blocking): {e}")


@router.get("/attempts")
async def get_writing_attempts(
    current_user: User = Depends(get_current_user)
):
    """
    Returns all writing attempts for the current learner.
    Used by the Progress Dashboard.
    """
    if not current_user.learner_id:
        return {"attempts": []}

    from app.services.memory_service import get_attempts
    attempts = get_attempts(current_user.learner_id, section="Writing")
    return {"attempts": attempts}
