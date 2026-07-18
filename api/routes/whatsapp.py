"""
api/routes/whatsapp.py — Meta WhatsApp Cloud API webhook

GET  /whatsapp/webhook — Meta verification handshake (one-time setup)
POST /whatsapp/webhook — Incoming messages from WhatsApp users

Message flow:
  1. Incoming message received
  2. Resolve learner_id from whatsapp_number (stored in users.whatsapp_number)
  3. Run Qwen agent with tool-calling → reply text
  4. Send reply via WhatsApp Cloud API
  5. If account not linked: ask for email, then link on next message

Conversation history is kept in-memory per phone number (last 6 messages).
In production this could move to Redis, but for a demo in-memory is fine.
"""

import os
from collections import defaultdict
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.db.database import SessionLocal
from api.auth.models import User
from app.services.whatsapp_service import run_qwen_agent, send_whatsapp_message

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "qonda_verify_2026")

# In-memory conversation history: phone_number → [{role, content}, ...]
_history: dict[str, list] = defaultdict(list)

# Pending email collection: phone_number → True (waiting for email)
_awaiting_email: set[str] = set()


def _get_learner_id_by_phone(phone: str) -> str | None:
    """Look up learner_id by WhatsApp phone number."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.whatsapp_number == phone).first()
        return user.learner_id if user else None
    finally:
        db.close()


def _link_phone_to_learner(phone: str, learner_id: str, email: str) -> bool:
    """Store the WhatsApp number on the user record."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user or not user.learner_id:
            return False
        user.whatsapp_number = phone
        db.commit()
        return True
    finally:
        db.close()


# ─── GET: Meta webhook verification ──────────────────────────────────────────

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta calls this once during webhook setup to verify ownership."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


# ─── POST: Incoming messages ──────────────────────────────────────────────────

@router.post("/webhook")
async def receive_message(request: Request):
    """Receive and process incoming WhatsApp messages."""
    body = await request.json()

    # Navigate the Meta webhook payload structure
    try:
        entry    = body["entry"][0]
        change   = entry["changes"][0]
        value    = change["value"]

        # Ignore status updates (delivered, read, etc.)
        if "messages" not in value:
            return {"status": "ignored"}

        message  = value["messages"][0]
        phone    = message["from"]
        msg_type = message.get("type", "")

        # Only handle text messages for now
        if msg_type != "text":
            send_whatsapp_message(phone, "I can only read text messages right now. Type something!")
            return {"status": "non-text ignored"}

        text = message["text"]["body"].strip()
    except (KeyError, IndexError):
        return {"status": "ignored"}

    # ── Resolve learner identity ───────────────────────────────────────────────

    learner_id = _get_learner_id_by_phone(phone)

    # Handle pending email collection
    if phone in _awaiting_email:
        # User just sent their email — try to link
        _awaiting_email.discard(phone)
        email = text.strip()

        # Run agent with the email so it calls find_learner
        history = _history[phone]
        reply = run_qwen_agent(
            user_message=f"My Qonda email is: {email}",
            learner_id=None,
            conversation_history=history,
        )
        # Check if link succeeded
        learner_id = _get_learner_id_by_phone(phone)
        if not learner_id:
            # Agent called find_learner; try to persist the mapping
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.email == email.lower()).first()
                if user and user.learner_id:
                    user.whatsapp_number = phone
                    db.commit()
                    learner_id = user.learner_id
            finally:
                db.close()

        _history[phone].append({"role": "assistant", "content": reply})
        send_whatsapp_message(phone, reply)
        return {"status": "ok"}

    # New user — ask for email
    if not learner_id:
        _awaiting_email.add(phone)
        greeting = (
            "👋 Hi! I'm Qonda, your AI IELTS coach.\n\n"
            "To connect your account, what's the email address you registered with on Qonda? "
            "(ielts.qonda.xyz)"
        )
        send_whatsapp_message(phone, greeting)
        return {"status": "ok"}

    # ── Known learner — run Qwen agent ────────────────────────────────────────

    history = _history[phone]
    history.append({"role": "user", "content": text})

    reply = run_qwen_agent(
        user_message=text,
        learner_id=learner_id,
        conversation_history=history[:-1],  # history before this message
    )

    history.append({"role": "assistant", "content": reply})

    # Keep history bounded
    if len(history) > 20:
        _history[phone] = history[-20:]

    send_whatsapp_message(phone, reply)
    return {"status": "ok"}
