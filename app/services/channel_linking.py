"""
Linking a Telegram chat or WhatsApp number to a BandUp account.

The learner creates a one-time code while signed in to the web app, then
sends it to the bot. Possessing the code proves account ownership; typing
an email address does not.
"""
import hashlib
import os
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from app.db.database import SessionLocal
from api.auth.models import ChannelLinkCode, User

CHANNELS = {"telegram": "telegram_chat_id", "whatsapp": "whatsapp_number"}
CODE_TTL = timedelta(minutes=10)
# No 0/O, 1/I/L — codes are read off a screen and typed on a phone.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
# The whole message must be the code (optionally after /start or LINK), so
# ordinary 8-letter words like "strength" are never mistaken for one.
CODE_PATTERN = re.compile(rf"^\s*(?:/START\s+|LINK\s+)?([{ALPHABET}]{{4}})[- ]?([{ALPHABET}]{{4}})\s*$")

MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW_SECONDS = 15 * 60
_failed_attempts: dict[str, deque] = defaultdict(deque)


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def format_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


def extract_code(text: str) -> str | None:
    """A message that is a link code: 'ABCD-2345', '/start ABCD2345' or 'link abcd 2345'."""
    match = CODE_PATTERN.match((text or "").upper())
    return match.group(1) + match.group(2) if match else None


def create_link_code(user_id: str, channel: str) -> dict:
    """Issues a fresh code for this user + channel, replacing any unused one."""
    if channel not in CHANNELS:
        raise ValueError(f"Unknown channel: {channel}")
    code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    expires_at = datetime.utcnow() + CODE_TTL
    db = SessionLocal()
    try:
        db.query(ChannelLinkCode).filter(
            ChannelLinkCode.user_id == user_id, ChannelLinkCode.channel == channel
        ).delete()
        db.add(ChannelLinkCode(code_hash=_hash(code), user_id=user_id, channel=channel, expires_at=expires_at))
        db.commit()
    finally:
        db.close()
    return {"code": format_code(code), "expires_at": expires_at.isoformat() + "Z", "deep_link": _deep_link(channel, code)}


def _deep_link(channel: str, code: str) -> str | None:
    if channel == "telegram" and os.getenv("TELEGRAM_BOT_USERNAME"):
        return f"https://t.me/{os.getenv('TELEGRAM_BOT_USERNAME')}?start={code}"
    if channel == "whatsapp" and os.getenv("WHATSAPP_DISPLAY_NUMBER"):
        digits = re.sub(r"\D", "", os.getenv("WHATSAPP_DISPLAY_NUMBER"))
        return f"https://wa.me/{digits}?text=LINK%20{format_code(code)}"
    return None


def is_rate_limited(external_id: str) -> bool:
    attempts = _failed_attempts[external_id]
    while attempts and attempts[0] < time.time() - ATTEMPT_WINDOW_SECONDS:
        attempts.popleft()
    return len(attempts) >= MAX_FAILED_ATTEMPTS


def redeem_link_code(code: str, channel: str, external_id: str) -> User | None:
    """
    Links external_id (chat id / phone) to the code's owner and consumes the
    code. Returns the linked user, or None if the code is invalid, expired,
    for another channel, or this sender is rate-limited.
    """
    if is_rate_limited(external_id):
        return None
    db = SessionLocal()
    try:
        row = db.query(ChannelLinkCode).filter(ChannelLinkCode.code_hash == _hash(code)).first()
        valid = row and row.channel == channel and row.expires_at > datetime.utcnow()
        user = db.query(User).filter(User.user_id == row.user_id).first() if valid else None
        if not user or not user.learner_id:
            _failed_attempts[external_id].append(time.time())
            return None

        column = CHANNELS[channel]
        # One chat/number belongs to exactly one account.
        db.query(User).filter(getattr(User, column) == external_id, User.user_id != user.user_id).update(
            {column: None}, synchronize_session=False
        )
        setattr(user, column, external_id)
        db.delete(row)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        _failed_attempts.pop(external_id, None)
        return user
    finally:
        db.close()


def learner_for(channel: str, external_id: str) -> str | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(getattr(User, CHANNELS[channel]) == external_id).first()
        return user.learner_id if user else None
    finally:
        db.close()


def link_status(user_id: str) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        return {channel: bool(user and getattr(user, column)) for channel, column in CHANNELS.items()}
    finally:
        db.close()


def unlink(user_id: str, channel: str) -> None:
    db = SessionLocal()
    try:
        db.query(User).filter(User.user_id == user_id).update({CHANNELS[channel]: None})
        db.query(ChannelLinkCode).filter(
            ChannelLinkCode.user_id == user_id, ChannelLinkCode.channel == channel
        ).delete()
        db.commit()
    finally:
        db.close()
