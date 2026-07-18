import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user
from api.auth.models import User
from app.services.chat_coach_service import (
    start_chat_session,
    continue_chat_session
)
from app.utils.logger import get_logger

logger = get_logger("api.routes.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


class ContinueChatRequest(BaseModel):
    system_prompt: str
    history: list
    message: str
    section: Optional[str] = "Writing"
    session_id: Optional[str] = None


@router.get("/context")
async def get_chat_context(
    section: str = "Writing",
    current_user: User = Depends(get_current_user)
):
    """
    Returns learner context instantly — no Qwen call, DB only.

    React uses this to show a preview card ("Your Writing Tutor
    is focusing on Cohesive Devices — Rank 1, 3 sessions to rank up")
    while the AI opening message is being generated.

    This dramatically reduces perceived wait time from ~10s to ~0.5s.
    """
    if not current_user.learner_id:
        return {"has_history": False}

    valid_sections = ["Writing", "Reading", "Speaking", "Listening"]
    if section not in valid_sections:
        section = "Writing"

    try:
        from app.services.memory_service import build_chat_coach_context
        context = build_chat_coach_context(current_user.learner_id, section)

        if not context["has_history"]:
            return {"has_history": False, "section": section}

        weakest = context.get("weakest_skill", {})
        skill_def = context.get("skill_definition", {})

        return {
            "has_history": True,
            "section": section,
            "weakest_skill_name": skill_def.get("skill_name", ""),
            "weakest_skill_category": skill_def.get("category_name", ""),
            "current_rank": weakest.get("current_rank", 1),
            "rank_name": weakest.get("rank_name", "Beginner"),
            "sessions_to_rank_up": max(0, 3 - weakest.get("clean_streak", 0))
        }

    except Exception as e:
        logger.warning(f"Context fetch failed: {e}")
        return {"has_history": False, "section": section}


@router.get("/start")
async def start_chat(
    section: str = "Writing",
    current_user: User = Depends(get_current_user)
):
    """
    Starts a new specialist tutor session for the given IELTS section.

    Each section activates a different specialist tutor with
    section-specific knowledge, strategies and system prompt.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    valid_sections = ["Writing", "Reading", "Speaking", "Listening"]
    if section not in valid_sections:
        section = "Writing"

    try:
        result = start_chat_session(
            learner_id=current_user.learner_id,
            section=section
        )

        return {
            "success": True,
            "message": result["message"],
            "state": result["state"],
            "has_history": result["has_history"],
            "section": result["section"],
            "system_prompt": result.get("system_prompt", ""),
            "session_id": result.get("session_id"),
            "pedagogy": result.get("pedagogy")
        }

    except Exception as e:
        logger.error(f"Chat start failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Could not start tutor session: {str(e)}"
        )


@router.post("/continue")
async def continue_chat(
    request: ContinueChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Continues an existing tutor session with a new learner message.

    When the tutor reaches bridge_to_practice: micro-memories are
    extracted AND the Coach interprets the session's pedagogical
    evidence in the background (hint dependency, support fading).
    """
    try:
        result = continue_chat_session(
            system_prompt=request.system_prompt,
            conversation_history=request.history,
            learner_message=request.message,
            learner_id=current_user.learner_id,
            section=request.section,
            session_id=request.session_id
        )

        # Coach interprets the session evidence once tutoring concludes
        if result.get("session_completed") and request.session_id:
            from app.services.coach_service import coach_tutor_session
            background_tasks.add_task(
                coach_tutor_session,
                current_user.learner_id,
                request.section,
                request.session_id
            )

        return {
            "success": True,
            "message": result["message"],
            "state": result["state"],
            "memories_extracted": result.get("memories_extracted", 0)
        }

    except Exception as e:
        logger.error(f"Chat continue failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )
