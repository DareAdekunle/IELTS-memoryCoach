"""
app/services/schedule_service.py

Business logic for study schedule management.
Handles CRUD for study_schedules and orchestrates Google Calendar events.
"""

import json
import uuid
from typing import Optional

from app.db.database import SessionLocal
from app.db.models import StudySchedule, Learner, LearnerSkillRank


# ─── Public API ───────────────────────────────────────────────────────────────

def create_or_update_schedule(
    learner_id: str,
    days: list,
    study_time: str,
    duration_minutes: int,
    timezone: str,
) -> dict:
    """
    Create or replace the learner's study schedule.
    Google Calendar connection is a separate step (attach_google_calendar).
    """
    db = SessionLocal()
    try:
        existing = db.query(StudySchedule).filter(
            StudySchedule.learner_id == learner_id
        ).first()

        if existing:
            existing.days_of_week     = json.dumps(days)
            existing.study_time       = study_time
            existing.duration_minutes = duration_minutes
            existing.timezone         = timezone
            existing.is_active        = True
            db.commit()
            db.refresh(existing)
            return _to_dict(existing)

        schedule = StudySchedule(
            schedule_id      = str(uuid.uuid4()),
            learner_id       = learner_id,
            days_of_week     = json.dumps(days),
            study_time       = study_time,
            duration_minutes = duration_minutes,
            timezone         = timezone,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return _to_dict(schedule)
    finally:
        db.close()


def get_schedule(learner_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        s = db.query(StudySchedule).filter(
            StudySchedule.learner_id == learner_id,
            StudySchedule.is_active  == True,
        ).first()
        return _to_dict(s) if s else None
    finally:
        db.close()


def attach_google_calendar(
    learner_id: str,
    refresh_token: str,
    event_id: str,
    google_email: Optional[str] = None,
) -> Optional[dict]:
    """Store the Google Calendar refresh token and event ID after OAuth."""
    db = SessionLocal()
    try:
        s = db.query(StudySchedule).filter(
            StudySchedule.learner_id == learner_id
        ).first()
        if not s:
            return None
        s.google_refresh_token     = refresh_token
        s.google_calendar_event_id = event_id
        s.google_email             = google_email
        db.commit()
        db.refresh(s)
        return _to_dict(s)
    finally:
        db.close()


def detach_google_calendar(learner_id: str) -> bool:
    """Remove Google Calendar connection (tokens + event ID)."""
    db = SessionLocal()
    try:
        s = db.query(StudySchedule).filter(
            StudySchedule.learner_id == learner_id
        ).first()
        if not s:
            return False
        s.google_refresh_token     = None
        s.google_calendar_event_id = None
        s.google_email             = None
        db.commit()
        return True
    finally:
        db.close()


def cancel_schedule(learner_id: str) -> bool:
    """Deactivate the schedule. Caller is responsible for deleting calendar events."""
    db = SessionLocal()
    try:
        s = db.query(StudySchedule).filter(
            StudySchedule.learner_id == learner_id
        ).first()
        if not s:
            return False
        s.is_active = False
        db.commit()
        return True
    finally:
        db.close()


def get_schedule_raw(learner_id: str) -> Optional[StudySchedule]:
    """Return the raw ORM object (needed for calendar operations that need tokens)."""
    db = SessionLocal()
    try:
        return db.query(StudySchedule).filter(
            StudySchedule.learner_id == learner_id,
            StudySchedule.is_active  == True,
        ).first()
    finally:
        db.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_learner_test_date(learner_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        learner = db.query(Learner).filter(Learner.learner_id == learner_id).first()
        return learner.test_date if learner else None
    finally:
        db.close()


def get_learner_name(learner_id: str) -> str:
    db = SessionLocal()
    try:
        learner = db.query(Learner).filter(Learner.learner_id == learner_id).first()
        return learner.name if learner else "learner"
    finally:
        db.close()


def get_weakest_skill_label(learner_id: str) -> Optional[str]:
    """Return the display label of the learner's lowest-ranked assessed skill."""
    db = SessionLocal()
    try:
        rank = (
            db.query(LearnerSkillRank)
            .filter(
                LearnerSkillRank.learner_id == learner_id,
                LearnerSkillRank.total_evidence > 0,
            )
            .order_by(LearnerSkillRank.current_rank.asc())
            .first()
        )
        return rank.skill_id.replace("_", " ").title() if rank else None
    finally:
        db.close()


def _to_dict(s: StudySchedule) -> dict:
    return {
        "schedule_id":      s.schedule_id,
        "learner_id":       s.learner_id,
        "days":             json.loads(s.days_of_week) if s.days_of_week else [],
        "study_time":       s.study_time,
        "duration_minutes": s.duration_minutes,
        "timezone":         s.timezone,
        "has_calendar":     bool(s.google_refresh_token),
        "google_email":     s.google_email,
        "is_active":        s.is_active,
    }
