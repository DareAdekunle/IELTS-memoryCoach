"""
api/routes/telegram.py — Telegram Bot webhook

POST /telegram/webhook — Incoming messages from Telegram users

Message flow:
  1. Telegram POSTs the update to this endpoint
  2. Resolve learner_id from telegram_chat_id stored in users table
  3. New users: ask for Qonda email → find_learner → store mapping
  4. Known users: run Qwen agent with tool-calling → send reply
"""

from collections import defaultdict
from fastapi import APIRouter, Request, BackgroundTasks

from app.db.database import SessionLocal
from api.auth.models import User
from app.services.telegram_service import run_qwen_agent, send_message, send_typing

router = APIRouter(prefix="/telegram", tags=["telegram"])

# In-memory conversation history: chat_id → [{role, content}]
_history: dict[str, list] = defaultdict(list)

# Waiting for email: set of chat_ids
_awaiting_email: set[str] = set()


def _get_learner_id(chat_id: str) -> str | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        return user.learner_id if user else None
    finally:
        db.close()


def _link_chat_to_learner(chat_id: str, email: str) -> str | None:
    """Store telegram_chat_id on the matching user. Returns learner_id if successful."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user or not user.learner_id:
            return None
        user.telegram_chat_id = chat_id
        db.commit()
        return user.learner_id
    finally:
        db.close()


def _process_message(chat_id: str, text: str):
    """Handle a single incoming message. Runs in background to avoid Telegram timeout."""
    learner_id = _get_learner_id(chat_id)

    # ── Pending email collection ───────────────────────────────────────────────
    if chat_id in _awaiting_email:
        _awaiting_email.discard(chat_id)
        send_typing(chat_id)

        linked_learner_id = _link_chat_to_learner(chat_id, text.strip())

        if linked_learner_id:
            reply = run_qwen_agent(
                user_message=f"My Qonda email is: {text.strip()}",
                learner_id=linked_learner_id,
                conversation_history=[],
            )
        else:
            reply = (
                "I couldn't find a Qonda account for that email. "
                "Please check the address or register at ielts.qonda.xyz, then try again."
            )

        _history[chat_id].append({"role": "assistant", "content": reply})
        send_message(chat_id, reply)
        return

    # ── New user — ask for email ───────────────────────────────────────────────
    if not learner_id:
        _awaiting_email.add(chat_id)
        send_message(
            chat_id,
            "👋 Hi! I'm *Qonda*, your AI IELTS coach — powered by Qwen.\n\n"
            "To connect your account, what's the email you registered with at "
            "ielts.qonda.xyz?"
        )
        return

    # ── Keyword pre-filter — block obvious out-of-scope requests cheaply ─────
    _BLOCKED = [
        "api key", "apikey", ".env", "secret key", "access token", "auth token",
        "bearer token", "private key", "client secret", "webhook secret",
        "curl ", "bash ", "terminal", "command line", "sudo", "chmod",
        "openai", "anthropic", "gemini", "chatgpt", "llm api",
        "write code", "write a script", "write a function", "write a program",
        "help me code", "help me build", "help me set up", "help me install",
        "ignore your instructions", "ignore previous", "disregard your",
        "act as", "pretend you are", "you are now", "jailbreak",
    ]
    text_lower = text.lower()
    if any(kw in text_lower for kw in _BLOCKED):
        send_message(
            chat_id,
            "I'm your IELTS coach — I can only help with IELTS preparation. "
            "What would you like to work on today?"
        )
        return

    # ── Known learner — run Qwen agent ────────────────────────────────────────
    history = _history[chat_id]
    history.append({"role": "user", "content": text})

    send_typing(chat_id)

    reply = run_qwen_agent(
        user_message=text,
        learner_id=learner_id,
        conversation_history=history[:-1],
    )

    history.append({"role": "assistant", "content": reply})

    if len(history) > 20:
        _history[chat_id] = history[-20:]

    send_message(chat_id, reply)


@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Telegram updates. Process in background to return 200 immediately."""
    body = await request.json()

    try:
        message  = body.get("message") or body.get("edited_message")
        if not message:
            return {"ok": True}

        chat_id  = str(message["chat"]["id"])
        text     = message.get("text", "").strip()

        if not text:
            send_message(chat_id, "I can only read text messages. Type something!")
            return {"ok": True}

        # Handle /start command
        if text == "/start":
            _history[chat_id].clear()
            _awaiting_email.discard(chat_id)
            learner_id = _get_learner_id(chat_id)
            if learner_id:
                background_tasks.add_task(
                    _process_message, chat_id, "Hello, give me a quick coaching update"
                )
            else:
                _awaiting_email.add(chat_id)
                send_message(
                    chat_id,
                    "👋 Hi! I'm *Qonda*, your AI IELTS coach — powered by Qwen.\n\n"
                    "To connect your account, what's the email you registered with at "
                    "ielts.qonda.xyz?"
                )
            return {"ok": True}

        background_tasks.add_task(_process_message, chat_id, text)

    except (KeyError, TypeError):
        pass

    return {"ok": True}
