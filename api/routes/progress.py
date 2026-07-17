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
from app.services.scoring_service import get_cross_section_insights
from app.services.skill_taxonomy_service import (
    get_band_estimate,
    format_band,
    get_band_label
)
from app.services.profile_service import create_learner, get_learner

router = APIRouter(prefix="/progress", tags=["progress"])


class CreateProfileRequest(BaseModel):
    name: str
    target_score: float
    test_date: Optional[str] = None
    current_focus: str = "Writing"


@router.post("/profile")
async def create_profile(
    request: CreateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
async def get_profile(current_user: User = Depends(get_current_user)):
    if not current_user.learner_id:
        return {"learner": None}
    learner = get_learner(current_user.learner_id)
    return {"learner": learner}


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
            "skills_at_advanced": 0,
            "overall_band": None,
            "overall_band_display": "No band yet"
        }

    learner_id = current_user.learner_id
    writing_data = get_progress_data(learner_id, section="Writing")
    reading_data = get_progress_data(learner_id, section="Reading")
    memory_stats = get_memory_stats(learner_id)
    skill_summary = get_skill_progress_summary(learner_id, section="Writing")

    # Derive overall band from average rank across all assessed skills
    all_ranks = get_all_skill_ranks(learner_id, section="Writing")
    assessed = [s for s in all_ranks if s["total_evidence"] > 0]
    overall_band = None
    overall_band_display = "No band yet"

    if assessed:
        avg_band = sum(
            s["band"] for s in assessed if s["band"] is not None
        ) / len([s for s in assessed if s["band"] is not None])
        # Round to nearest 0.5
        overall_band = round(avg_band * 2) / 2
        overall_band_display = format_band(overall_band)

    return {
        "has_data": True,
        "writing_attempts": writing_data["total_attempts"],
        "reading_attempts": reading_data["total_attempts"],
        "active_memories": memory_stats["active_count"],
        "archived_memories": memory_stats["archived_count"],
        "skills_mastered": memory_stats["archived_count"],
        "average_skill_rank": skill_summary["average_rank"],
        "skills_at_advanced": skill_summary["skills_at_max"],
        "overall_band": overall_band,
        "overall_band_display": overall_band_display
    }


@router.get("/writing")
async def get_writing_progress(current_user: User = Depends(get_current_user)):
    if not current_user.learner_id:
        return {"total_attempts": 0, "attempts": [], "skill_trends": {}}
    return get_progress_data(current_user.learner_id, section="Writing")


@router.get("/reading")
async def get_reading_progress(current_user: User = Depends(get_current_user)):
    if not current_user.learner_id:
        return {"total_attempts": 0, "attempts": [], "skill_trends": {}}
    return get_progress_data(current_user.learner_id, section="Reading")


@router.get("/skills")
async def get_skill_ranks(
    section: str = "Writing",
    current_user: User = Depends(get_current_user)
):
    """
    Returns the learner's rank AND band estimate on all skills
    for a given section.

    Each skill now includes:
      current_rank:   1-5 (internal engine value)
      rank_name:      Beginner → Advanced
      band:           IELTS band estimate (4.0-8.5, None if no evidence)
      band_display:   "Band 6.5" or "No band yet"
      band_label:     "Competent", "Proficient" etc.
      clean_streak:   consecutive strengths toward next band
      total_evidence: total times this skill was assessed

    Band mapping:
      Rank 1, streak 0 → Band 4.0  |  streak 1+ → Band 4.5
      Rank 2, streak 0 → Band 5.0  |  streak 1+ → Band 5.5
      Rank 3, streak 0 → Band 6.0  |  streak 1+ → Band 6.5
      Rank 4, streak 0 → Band 7.0  |  streak 1+ → Band 7.5
      Rank 5, streak 0 → Band 8.0  |  streak 1+ → Band 8.5

    A weakness resets streak to 0, dropping the band back to base
    within that rank — giving realistic downward movement without
    destabilising the underlying rank engine.
    """
    if not current_user.learner_id:
        return {"skills": [], "summary": {}, "section": section}

    valid_sections = ["Writing", "Reading", "Speaking", "Listening"]
    if section not in valid_sections:
        section = "Writing"

    learner_id = current_user.learner_id
    all_ranks = get_all_skill_ranks(learner_id, section=section)
    summary = get_skill_progress_summary(learner_id, section=section)

    # Derive overall band for this section
    assessed = [s for s in all_ranks if s.get("total_evidence", 0) > 0]
    section_band = None
    section_band_display = "No band yet"

    if assessed:
        valid_bands = [s["band"] for s in assessed if s.get("band") is not None]
        if valid_bands:
            avg = sum(valid_bands) / len(valid_bands)
            section_band = round(avg * 2) / 2
            section_band_display = format_band(section_band)

    return {
        "skills": all_ranks,
        "summary": {
            **summary,
            "section_band": section_band,
            "section_band_display": section_band_display,
            "section_band_label": get_band_label(section_band)
        },
        "section": section
    }

@router.get("/insights")
async def get_insights(current_user: User = Depends(get_current_user)):
    """
    Returns cross-section skill insights — patterns that appear across
    multiple IELTS sections, indicating core skill gaps rather than
    section-specific weaknesses.

    Also returns per-section band estimates and overall band.
    Used by the Dashboard and Skill Mastery page.
    """
    if not current_user.learner_id:
        return {
            "has_insights": False,
            "cross_section_patterns": [],
            "section_bands": {},
            "overall_band": None,
            "overall_band_display": "No band yet",
            "strongest_section": None,
            "weakest_section": None,
            "sections_assessed": 0
        }

    try:
        return get_cross_section_insights(current_user.learner_id)
    except Exception as e:
        return {
            "has_insights": False,
            "cross_section_patterns": [],
            "section_bands": {},
            "overall_band": None,
            "overall_band_display": "No band yet",
            "strongest_section": None,
            "weakest_section": None,
            "sections_assessed": 0
        }
