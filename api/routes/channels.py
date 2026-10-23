"""
api/routes/channels.py — connect chat channels (Telegram, WhatsApp) to an account

GET    /channels/status               — which channels are linked
POST   /channels/{channel}/link-code  — one-time code to send to the bot
DELETE /channels/{channel}            — disconnect
"""
from fastapi import APIRouter, Depends, HTTPException

from api.auth.models import User
from api.dependencies import get_current_user
from app.services import channel_linking

router = APIRouter(prefix="/channels", tags=["channels"])


def _check_channel(channel: str) -> None:
    if channel not in channel_linking.CHANNELS:
        raise HTTPException(status_code=404, detail="Unknown channel")


@router.get("/status")
async def get_status(current_user: User = Depends(get_current_user)):
    return channel_linking.link_status(current_user.user_id)


@router.post("/{channel}/link-code")
async def create_link_code(channel: str, current_user: User = Depends(get_current_user)):
    _check_channel(channel)
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")
    return channel_linking.create_link_code(current_user.user_id, channel)


@router.delete("/{channel}")
async def disconnect(channel: str, current_user: User = Depends(get_current_user)):
    _check_channel(channel)
    channel_linking.unlink(current_user.user_id, channel)
    return channel_linking.link_status(current_user.user_id)
