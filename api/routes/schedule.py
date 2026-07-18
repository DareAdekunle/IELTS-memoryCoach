"""
api/routes/schedule.py

Study schedule API — create/read/update schedules and manage
Google Calendar integration via OAuth.

Routes:
  POST   /schedule/setup                  — save study schedule
  GET    /schedule/me                     — get current schedule
  DELETE /schedule/cancel                 — cancel schedule + remove calendar events
  GET    /schedule/calendar/connect       — get Google OAuth URL
  GET    /schedule/calendar/callback      — OAuth callback (redirect from Google)
  DELETE /schedule/calendar/disconnect    — remove Google Calendar connection
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List

from api.auth.router import get_current_user
from api.auth.models import User
from app.services import schedule_service, calendar_service

router = APIRouter(prefix="/schedule", tags=["schedule"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ScheduleSetupRequest(BaseModel):
    days: List[str]               # ["Mon", "Wed", "Fri"]
    study_time: str               # "07:00"
    duration_minutes: int = 30
    timezone: str = "UTC"


# ─── Schedule CRUD ────────────────────────────────────────────────────────────

@router.post("/setup")
async def setup_schedule(
    body: ScheduleSetupRequest,
    current_user: User = Depends(get_current_user),
):
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")

    valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    bad = [d for d in body.days if d not in valid_days]
    if bad:
        raise HTTPException(status_code=422, detail=f"Invalid days: {bad}")
    if not body.days:
        raise HTTPException(status_code=422, detail="Select at least one study day")
    if body.duration_minutes not in (15, 30, 45, 60):
        raise HTTPException(status_code=422, detail="Duration must be 15, 30, 45 or 60 minutes")

    schedule = schedule_service.create_or_update_schedule(
        learner_id       = current_user.learner_id,
        days             = body.days,
        study_time       = body.study_time,
        duration_minutes = body.duration_minutes,
        timezone         = body.timezone,
    )
    return schedule


@router.get("/me")
async def get_my_schedule(current_user: User = Depends(get_current_user)):
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")
    schedule = schedule_service.get_schedule(current_user.learner_id)
    if not schedule:
        return {"has_schedule": False}
    return {"has_schedule": True, **schedule}


@router.delete("/cancel")
async def cancel_schedule(current_user: User = Depends(get_current_user)):
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")

    raw = schedule_service.get_schedule_raw(current_user.learner_id)
    if raw and raw.google_refresh_token and raw.google_calendar_event_id:
        calendar_service.delete_study_events(
            raw.google_refresh_token, raw.google_calendar_event_id
        )

    cancelled = schedule_service.cancel_schedule(current_user.learner_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="No active schedule found")
    return {"cancelled": True}


# ─── Google Calendar OAuth ────────────────────────────────────────────────────

@router.get("/calendar/connect")
async def calendar_connect(current_user: User = Depends(get_current_user)):
    """Return the Google OAuth URL the frontend should redirect the user to."""
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")

    schedule = schedule_service.get_schedule(current_user.learner_id)
    if not schedule:
        raise HTTPException(
            status_code=400,
            detail="Set up a study schedule before connecting Google Calendar"
        )

    auth_url = calendar_service.get_auth_url(current_user.learner_id)
    return {"auth_url": auth_url}


@router.get("/calendar/callback")
async def calendar_callback(code: str, state: str):
    """
    Google redirects here after the user grants calendar access.
    Exchanges the code for tokens, creates calendar events, then
    redirects the user back to the frontend Study Plan page.
    """
    try:
        payload = calendar_service.decode_state(state)
        learner_id = payload["learner_id"]
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}/study-plan?error=bad_state")

    try:
        tokens = calendar_service.exchange_code(code)
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_URL}/study-plan?error=token_exchange")

    raw = schedule_service.get_schedule_raw(learner_id)
    if not raw:
        return RedirectResponse(f"{FRONTEND_URL}/study-plan?error=no_schedule")

    import json
    days             = json.loads(raw.days_of_week)
    test_date        = schedule_service.get_learner_test_date(learner_id)
    weakest_skill    = schedule_service.get_weakest_skill_label(learner_id)
    learner_name     = schedule_service.get_learner_name(learner_id)

    try:
        event_id = calendar_service.create_study_events(
            refresh_token    = tokens["refresh_token"],
            days             = days,
            study_time       = raw.study_time,
            duration_minutes = raw.duration_minutes,
            timezone         = raw.timezone,
            test_date        = test_date,
            weakest_skill    = weakest_skill,
            learner_name     = learner_name,
        )
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_URL}/study-plan?error=calendar_create")

    schedule_service.attach_google_calendar(
        learner_id    = learner_id,
        refresh_token = tokens["refresh_token"],
        event_id      = event_id,
        google_email  = tokens.get("email"),
    )

    return RedirectResponse(f"{FRONTEND_URL}/study-plan?calendar=connected")


@router.delete("/calendar/disconnect")
async def calendar_disconnect(current_user: User = Depends(get_current_user)):
    """Remove Google Calendar tokens and delete future events."""
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")

    raw = schedule_service.get_schedule_raw(current_user.learner_id)
    if raw and raw.google_refresh_token and raw.google_calendar_event_id:
        calendar_service.delete_study_events(
            raw.google_refresh_token, raw.google_calendar_event_id
        )

    schedule_service.detach_google_calendar(current_user.learner_id)
    return {"disconnected": True}
