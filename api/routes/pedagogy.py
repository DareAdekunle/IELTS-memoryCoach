"""
api/routes/pedagogy.py

Read-only pedagogy endpoints for the UI:
  - per-criterion stages, support levels and target descriptors
  - framework registry lookups
  - hint dependency metrics

Plan creation and event recording are internal (they happen inside
the Tutor session flow) — no public write endpoints.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.auth.models import User
from app.utils.logger import get_logger

logger = get_logger("api.routes.pedagogy")

router = APIRouter(prefix="/pedagogy", tags=["pedagogy"])

VALID_SECTIONS = ["Writing", "Reading", "Speaking", "Listening"]


@router.get("/criterion-stages")
async def criterion_stages(
    section: str = "Writing",
    current_user: User = Depends(get_current_user)
):
    """
    Per-criterion pedagogical state for the current learner:
    band, stage, support level, target descriptor, hint dependency.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )
    if section not in VALID_SECTIONS:
        section = "Writing"

    try:
        from app.pedagogy.stage_resolver import get_all_criterion_stages
        from app.pedagogy.stages import LearnerStage
        from app.pedagogy.session_policy import conditions_for
        from app.services.pedagogical_event_service import get_hint_dependency

        stages = get_all_criterion_stages(current_user.learner_id, section)

        # Practice conditions follow the WEAKEST criterion's stage —
        # the most conservative gate wins until every criterion clears it
        stage_order = ["foundations", "guided_control",
                       "independent_control", "automatization"]
        assessed = [s for s in stages if s["band"] is not None]
        weakest_stage = min(
            (s["stage"] for s in assessed),
            key=stage_order.index,
            default="foundations",
        )

        return {
            "section": section,
            "criterion_stages": stages,
            "practice_conditions": conditions_for(
                section, LearnerStage(weakest_stage)
            ).to_dict(),
            "hint_dependency": get_hint_dependency(
                current_user.learner_id, section
            ),
        }
    except Exception as e:
        logger.error(f"Criterion stages failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/frameworks")
async def list_frameworks(
    section: str = None,
    current_user: User = Depends(get_current_user)
):
    """The pedagogical framework registry (optionally per section)."""
    from app.pedagogy.registry import (
        get_frameworks_for_section, get_shared_spine, _load
    )

    frameworks = (
        get_frameworks_for_section(section)
        if section else _load()["frameworks"]
    )
    return {
        "frameworks": frameworks,
        "shared_spine": get_shared_spine(),
    }
