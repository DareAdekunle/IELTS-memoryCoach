from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    """
    Stores user authentication data.
    Separate from the learner profile (Learner table) — a User
    can have one linked Learner profile.

    password_hash is nullable because OAuth users don't have a
    password — they authenticate via Google only.
    """
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)   # null for OAuth users
    full_name = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)
    auth_provider = Column(String, default="local")  # "local" or "google"
    is_active = Column(Boolean, default=True)
    learner_id = Column(String, nullable=True)       # linked learner profile
    whatsapp_number  = Column(String, nullable=True, index=True)  # set only via a link code
    telegram_chat_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime, nullable=True)


class ChannelLinkCode(Base):
    """
    One-time code that links a Telegram chat or WhatsApp number to a user.
    The learner generates it in the web app (proving they own the account)
    and sends it to the bot. Only a SHA-256 hash of the code is stored.
    """
    __tablename__ = "channel_link_codes"

    code_hash = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False)          # "telegram" | "whatsapp"
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
