import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user
from api.auth.models import User
from app.services.chat_coach_service import (
    start_chat_session,
    continue_chat_session
)

router = APIRouter(prefix="/chat", tags=["chat"])


class ContinueChatRequest(BaseModel):
    system_prompt: str
    history: list
    message: str


@router.get("/start")
async def start_chat(
    current_user: User = Depends(get_current_user)
):
    """
    Starts a new chat coaching session.
    Builds context from the learner's skill ranks and memories,
    then generates the coach's opening message.
    Returns the opening message, state, and system prompt
    needed for subsequent turns.
    """
    if not current_user.learner_id:
        raise HTTPException(
            status_code=400,
            detail="Please create a learner profile first"
        )

    try:
        result = start_chat_session(
            learner_id=current_user.learner_id,
            section="Writing"
        )
        return {
            "success": True,
            "message": result["message"],
            "state": result["state"],
            "has_history": result["has_history"],
            "system_prompt": result.get("system_prompt", "")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not start chat session: {str(e)}"
        )


@router.post("/continue")
async def continue_chat(
    request: ContinueChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Continues an existing chat session with a new learner message.
    Requires the full conversation history and system prompt
    from the session start — we don't persist chat history server-side.
    Returns the coach's reply and the new state.
    """
    try:
        result = continue_chat_session(
            system_prompt=request.system_prompt,
            conversation_history=request.history,
            learner_message=request.message
        )
        return {
            "success": True,
            "message": result["message"],
            "state": result["state"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )
