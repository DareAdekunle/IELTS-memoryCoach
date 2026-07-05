import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from dotenv import load_dotenv

from app.db.database import SessionLocal
from api.auth.models import User
from api.auth.schemas import (
    RegisterRequest, LoginRequest,
    TokenResponse, UserResponse, MessageResponse
)
from api.auth.utils import (
    hash_password, verify_password,
    create_access_token, generate_user_id
)
from api.dependencies import get_db, get_current_user

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

# ─── Google OAuth setup ───────────────────────────────────────────────────────
config = Config(environ={
    "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID", ""),
    "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET", "")
})

oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# ─── Username / Password Auth ─────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user with email, username and password.
    Returns a JWT token immediately so the user is logged in
    right after registering — no separate login step required.
    """
    # Check email not already taken
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )

    # Check username not already taken
    existing_username = db.query(User).filter(
        User.username == request.username
    ).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This username is already taken"
        )

    user_id = generate_user_id()

    user = User(
        user_id=user_id,
        email=request.email,
        username=request.username,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        auth_provider="local",
        last_login=datetime.utcnow()
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.user_id})

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        learner_id=user.learner_id
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Log in with email and password.
    Returns a JWT token on success.
    """
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token({"sub": user.user_id})

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        learner_id=user.learner_id
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the currently authenticated user's profile.
    React calls this on app load to check if the stored token is
    still valid and to get the user's details.
    """
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        auth_provider=current_user.auth_provider,
        learner_id=current_user.learner_id
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint. Since we use stateless JWT tokens, the actual
    token invalidation happens on the client side (React deletes the
    stored token). This endpoint exists so the client has a clean
    API to call and we can log the logout event if needed later.
    """
    return MessageResponse(message="Logged out successfully")


# ─── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login(request: Request):
    """
    Initiates the Google OAuth flow.
    Redirects the user to Google's login page.
    React calls this by navigating to this URL directly.
    """
    redirect_uri = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/auth/google/callback"
    )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """
    Google redirects back here after the user grants permission.
    We exchange the code for a token, get the user's Google profile,
    then either create a new account or log in to an existing one.
    Finally we redirect to the React frontend with a JWT token in
    the URL so React can store it and complete the login flow.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo")

        if not userinfo:
            raise HTTPException(
                status_code=400,
                detail="Could not get user info from Google"
            )

        google_id = userinfo["sub"]
        email = userinfo["email"]
        full_name = userinfo.get("name", "")

        # Check if user already exists by Google ID
        user = db.query(User).filter(User.google_id == google_id).first()

        if user is None:
            # Check if an account exists with this email (local auth)
            user = db.query(User).filter(User.email == email).first()

            if user:
                # Link Google to existing local account
                user.google_id = google_id
                user.auth_provider = "google"
            else:
                # Brand new user via Google
                user = User(
                    user_id=generate_user_id(),
                    email=email,
                    full_name=full_name,
                    google_id=google_id,
                    auth_provider="google",
                    is_active=True
                )
                db.add(user)

        user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(user)

        # Create JWT and redirect to React with token in URL
        jwt_token = create_access_token({"sub": user.user_id})

        redirect_url = (
            f"{FRONTEND_URL}/auth/callback"
            f"?token={jwt_token}"
            f"&user_id={user.user_id}"
            f"&email={email}"
        )

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        # On any OAuth error redirect to login page with error message
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=oauth_failed"
        )