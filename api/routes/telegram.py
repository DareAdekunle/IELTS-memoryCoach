"""
api/routes/telegram.py — Telegram Bot webhook

POST /telegram/webhook — incoming updates from Telegram

Requests must carry the X-Telegram-Bot-Api-Secret-Token header matching
TELEGRAM_WEBHOOK_SECRET (set via setWebhook's secret_token). Replies are
decided by app.services.bot_conversation and sent in the background so
Telegram gets an immediate 200.
"""
import hmac
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.services.bot_conversation import respond
from app.services.telegram_service import send_message, send_typing

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _verify_secret(request: Request) -> None:
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="Telegram webhook is not configured")
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


def _reply(chat_id: str, text: str) -> None:
    send_typing(chat_id)
    send_message(chat_id, respond("telegram", chat_id, text))


@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    _verify_secret(request)
    body = await request.json()

    message = body.get("message") or body.get("edited_message")
    if not message or "chat" not in message:
        return {"ok": True}

    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()
    if not text:
        background_tasks.add_task(send_message, chat_id, "I can only read text messages. Type something!")
        return {"ok": True}

    background_tasks.add_task(_reply, chat_id, text)
    return {"ok": True}
