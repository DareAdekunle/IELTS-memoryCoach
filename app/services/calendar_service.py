"""
app/services/calendar_service.py

Google Calendar integration for Qonda IELTS study scheduling.
Creates recurring study events in a learner's own Google Calendar
via OAuth (Option A — write to the learner's calendar directly).
"""

import os
import json
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_CALENDAR_REDIRECT_URI = os.getenv(
    "GOOGLE_CALENDAR_REDIRECT_URI",
    "http://localhost:8000/schedule/calendar/callback",
)

SCOPES = ["https://www.googleapis.com/auth/calendar.events",
          "https://www.googleapis.com/auth/userinfo.email",
          "openid"]

# RFC 5545 BYDAY codes
DAY_TO_RFC = {
    "Mon": "MO", "Tue": "TU", "Wed": "WE",
    "Thu": "TH", "Fri": "FR", "Sat": "SA", "Sun": "SU",
}


# ─── OAuth helpers ─────────────────────────────────────────────────────────────

def get_auth_url(learner_id: str) -> str:
    """Return the Google OAuth consent URL for calendar access."""
    from google_auth_oauthlib.flow import Flow
    flow = _make_flow()

    # PKCE — Google requires this for all OAuth flows
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    # Store code_verifier in state so the callback can retrieve it
    state = base64.urlsafe_b64encode(
        json.dumps({"learner_id": learner_id, "cv": code_verifier}).encode()
    ).decode()

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="false",
        prompt="consent",
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    return auth_url


def exchange_code(code: str, code_verifier: str = None) -> dict:
    """
    Exchange an OAuth authorisation code for tokens.
    Returns {"access_token": ..., "refresh_token": ..., "email": ...}
    """
    from google_auth_oauthlib.flow import Flow
    import googleapiclient.discovery as gd

    flow = _make_flow()
    fetch_kwargs = {"code": code}
    if code_verifier:
        fetch_kwargs["code_verifier"] = code_verifier
    flow.fetch_token(**fetch_kwargs)
    creds = flow.credentials

    # Get the user's email so we can display which account is linked
    service = gd.build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()

    return {
        "access_token":  creds.token,
        "refresh_token": creds.refresh_token,
        "email":         user_info.get("email", ""),
    }


def decode_state(state: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(state.encode()).decode())


# ─── Event management ──────────────────────────────────────────────────────────

def create_study_events(
    refresh_token: str,
    days: list,
    study_time: str,
    duration_minutes: int,
    timezone: str,
    test_date: Optional[str],
    weakest_skill: Optional[str] = None,
    learner_name: str = "learner",
) -> str:
    """
    Creates a recurring Google Calendar event series for study sessions.
    Returns the Google Calendar event ID (store this to update/delete later).
    """
    import googleapiclient.discovery as gd

    creds = _build_creds(refresh_token)
    service = gd.build("calendar", "v3", credentials=creds)

    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    hour, minute = map(int, study_time.split(":"))
    start_dt = _next_occurrence(days, hour, minute, tz)
    end_dt   = start_dt + timedelta(minutes=duration_minutes)

    byday = ",".join(DAY_TO_RFC[d] for d in days if d in DAY_TO_RFC)
    if test_date:
        until_dt  = datetime.strptime(test_date, "%Y-%m-%d")
        until_str = until_dt.strftime("%Y%m%dT235959Z")
        rrule = f"RRULE:FREQ=WEEKLY;BYDAY={byday};UNTIL={until_str}"
    else:
        rrule = f"RRULE:FREQ=WEEKLY;BYDAY={byday};COUNT=52"

    skill_line = f"\n\nSession focus: {weakest_skill}" if weakest_skill else ""
    description = (
        f"Your Qonda IELTS study session, {learner_name}.{skill_line}\n\n"
        f"Open Qonda: https://ielts.qonda.xyz\n\n"
        f"Qonda — Grasp English. Retain for life."
    )

    event = {
        "summary":     f"Qonda IELTS — {duration_minutes} min practice",
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": timezone},
        "recurrence": [rrule],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 60},
                {"method": "popup",  "minutes": 10},
            ],
        },
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    return created["id"]


def delete_study_events(refresh_token: str, event_id: str) -> None:
    """Deletes the recurring event series from the learner's calendar."""
    import googleapiclient.discovery as gd
    try:
        creds   = _build_creds(refresh_token)
        service = gd.build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except Exception:
        pass  # already deleted or token expired — non-fatal


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _next_occurrence(days: list, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    """Find the next future datetime matching one of the given weekday names."""
    now = datetime.now(tz)
    for offset in range(1, 9):
        candidate = (now + timedelta(days=offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate.strftime("%a") in days:
            return candidate
    return (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def _make_flow():
    from google_auth_oauthlib.flow import Flow
    client_config = {
        "web": {
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_CALENDAR_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=GOOGLE_CALENDAR_REDIRECT_URI
    )


def _build_creds(refresh_token: str):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds
