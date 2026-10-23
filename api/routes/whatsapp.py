"""
api/routes/whatsapp.py — Meta WhatsApp Cloud API webhook

GET  /whatsapp/webhook — Meta verification handshake (one-time setup)
POST /whatsapp/webhook — incoming messages

POSTs must carry X-Hub-Signature-256 = HMAC-SHA256 of the raw body keyed
with WHATSAPP_APP_SECRET. Meta retries deliveries it thinks failed, so
message ids are de-duplicated. Replies are decided by
app.services.bot_conversation and sent in the background.
"""
import hashlib
import hmac
import json
import os
from collections import OrderedDict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.services.bot_conversation import respond
from app.services.whatsapp_service import send_whatsapp_message

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

_seen_message_ids: OrderedDict[str, None] = OrderedDict()
_SEEN_LIMIT = 2000


def _verify_signature(raw_body: bytes, header: str) -> None:
    secret = os.getenv("WHATSAPP_APP_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="WhatsApp webhook is not configured")
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(header or "", expected):
        raise HTTPException(status_code=403, detail="Invalid signature")


def _already_seen(message_id: str) -> bool:
    if message_id in _seen_message_ids:
        return True
    _seen_message_ids[message_id] = None
    if len(_seen_message_ids) > _SEEN_LIMIT:
        _seen_message_ids.popitem(last=False)
    return False


def _reply(phone: str, text: str) -> None:
    send_whatsapp_message(phone, respond("whatsapp", phone, text))


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta calls this once during webhook setup to verify ownership."""
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if expected and hub_mode == "subscribe" and hmac.compare_digest(hub_verify_token or "", expected):
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256", ""))

    try:
        value = json.loads(raw_body)["entry"][0]["changes"][0]["value"]
        message = value["messages"][0]  # absent for delivery/read status updates
        phone = message["from"]
    except (KeyError, IndexError, ValueError):
        return {"status": "ignored"}

    if message.get("id") and _already_seen(message["id"]):
        return {"status": "duplicate"}

    if message.get("type") != "text":
        background_tasks.add_task(send_whatsapp_message, phone, "I can only read text messages right now. Type something!")
        return {"status": "ok"}

    background_tasks.add_task(_reply, phone, message["text"]["body"])
    return {"status": "ok"}
