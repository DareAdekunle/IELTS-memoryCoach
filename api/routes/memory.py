import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from typing import Optional

from api.dependencies import get_current_user
from api.auth.models import User
from app.services.memory_service import (
    get_all_memories,
    get_memory_stats,
    get_relevant_memories
)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/all")
async def get_all_learner_memories(
    current_user: User = Depends(get_current_user)
):
    """
    Returns all memories for the current learner grouped by status.
    Used by the Memory Dashboard page.
    """
    if not current_user.learner_id:
        return {
            "active": [],
            "archived": [],
            "stats": {}
        }

    learner_id = current_user.learner_id
    memories = get_all_memories(learner_id)
    stats = get_memory_stats(learner_id)

    return {
        "active": memories["active"],
        "archived": memories["archived"],
        "stats": stats
    }


@router.get("/active")
async def get_active_memories(
    section: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Returns active memories, optionally filtered by section.
    Used by the memory panel on Writing and Reading Coach pages.
    """
    if not current_user.learner_id:
        return {"memories": []}

    memories = get_relevant_memories(
        current_user.learner_id,
        section=section or "Writing",
        limit=5
    )
    return {"memories": memories}


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user)
):
    """Returns memory statistics for the dashboard summary."""
    if not current_user.learner_id:
        return {
            "total_memories": 0,
            "active_count": 0,
            "archived_count": 0,
            "weakness_count": 0,
            "strength_count": 0,
            "avg_confidence": 0
        }

    return get_memory_stats(current_user.learner_id)

@router.get("/timeline")
async def get_memory_timeline(
    current_user: User = Depends(get_current_user)
):
    """
    Returns memory evolution data for the timeline visualization.
    Shows how each memory's confidence changed across attempts,
    making the MemoryAgent's learning process visible.
    """
    if not current_user.learner_id:
        return {"timeline": [], "attempts_count": 0}

    from app.db.database import SessionLocal
    from app.db.models import LearnerMemory, PracticeAttempt
    from sqlalchemy import desc

    db = SessionLocal()
    try:
        # Get all memories including archived
        memories = db.query(LearnerMemory).filter(
            LearnerMemory.learner_id == current_user.learner_id
        ).order_by(LearnerMemory.created_at.asc()).all()

        # Get attempt count per section for context
        attempts = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == current_user.learner_id
        ).order_by(PracticeAttempt.created_at.asc()).all()

        timeline = []
        for mem in memories:
            timeline.append({
                "memory_id": mem.memory_id,
                "skill": mem.skill,
                "section": mem.section,
                "memory_type": mem.memory_type,
                "memory_text": mem.memory_text,
                "confidence": float(mem.confidence or 0),
                "evidence_count": mem.evidence_count or 0,
                "status": mem.status,
                "created_at": str(mem.created_at),
                "updated_at": str(mem.updated_at)
            })

        return {
            "timeline": timeline,
            "attempts_count": len(attempts),
            "total_memories": len(memories),
            "active_count": len([m for m in memories if m.status == "active"]),
            "archived_count": len([m for m in memories if m.status == "archived"])
        }
    finally:
        db.close()
