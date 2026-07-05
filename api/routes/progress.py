import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db
from api.auth.models import User
from app.services.memory_service import (
    get_progress_data,
    get_memory_stats,
    get_skill_progress_summary,
    get_all_skill_ranks
)
from app.services.profile_service import create_learner, get_learner

router = APIRouter(prefix="/progress", tags=["progress"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateProfileRequest(BaseModel):
    name: str
    target_score: float
    test_date: Optional[str] = None
    current_focus: str = "Writing"


# ─── Profile routes ───────────────────────────────────────────────────────────

@router.post("/profile")
async def create_profile(
    request: CreateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a learner profile and links it to the user account.
    Called during onboarding — only needs to run once per user.
    """
    if current_user.learner_id:
        learner = get_learner(current_user.learner_id)
        return {"learner": learner, "created": False}

    learner_id = create_learner(
        name=request.name,
        target_score=request.target_score,
        test_date=request.test_date or "",
        current_focus=request.current_focus
    )

    current_user.learner_id = learner_id
    db.commit()

    learner = get_learner(learner_id)
    return {"learner": learner, "created": True}


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Returns the learner profile linked to this user."""
    if not current_user.learner_id:
        return {"learner": None}

    learner = get_learner(current_user.learner_id)
    return {"learner": learner}


# ─── Progress routes ──────────────────────────────────────────────────────────

@router.get("/summary")
async def get_summary(current_user: User = Depends(get_current_user)):
    """Overall progress summary across all sections."""
    if not current_user.learner_id:
        return {
            "has_data": False,
            "writing_attempts": 0,
            "reading_attempts": 0,
            "active_memories": 0,
            "skills_mastered": 0,
            "average_skill_rank": 0,
            "skills_at_advanced": 0
        }

    learner_id = current_user.learner_id
    writing_data = get_progress_data(learner_id, section="Writing")
    reading_data = get_progress_data(learner_id, section="Reading")
    memory_stats = get_memory_stats(learner_id)
    skill_summary = get_skill_progress_summary(learner_id, section="Writing")

    return {
        "has_data": True,
        "writing_attempts": writing_data["total_attempts"],
        "reading_attempts": reading_data["total_attempts"],
        "active_memories": memory_stats["active_count"],
        "archived_memories": memory_stats["archived_count"],
        "skills_mastered": memory_stats["archived_count"],
        "average_skill_rank": skill_summary["average_rank"],
        "skills_at_advanced": skill_summary["skills_at_max"]
    }


@router.get("/writing")
async def get_writing_progress(
    current_user: User = Depends(get_current_user)
):
    """Detailed writing progress data including score trends."""
    if not current_user.learner_id:
        return {"total_attempts": 0, "attempts": [], "skill_trends": {}}

    return get_progress_data(current_user.learner_id, section="Writing")


@router.get("/reading")
async def get_reading_progress(
    current_user: User = Depends(get_current_user)
):
    """Detailed reading progress data."""
    if not current_user.learner_id:
        return {"total_attempts": 0, "attempts": [], "skill_trends": {}}

    return get_progress_data(current_user.learner_id, section="Reading")


@router.get("/skills")
async def get_skill_ranks(
    current_user: User = Depends(get_current_user)
):
    """Returns the learner's rank on all 13 writing sub-skills."""
    if not current_user.learner_id:
        return {"skills": [], "summary": {}}

    learner_id = current_user.learner_id
    all_ranks = get_all_skill_ranks(learner_id, section="Writing")
    summary = get_skill_progress_summary(learner_id, section="Writing")

    return {
        "skills": all_ranks,
        "summary": summary
    }
