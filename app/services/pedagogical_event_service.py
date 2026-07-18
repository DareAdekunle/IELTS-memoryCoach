"""
app/services/pedagogical_event_service.py

Records and queries pedagogical evidence — session events and hint
events. The Tutor records what happened (via parsed action tags);
the Coach reads this evidence to decide what it means.
"""

import json
import uuid
from datetime import datetime

from app.db.database import SessionLocal
from app.db.models import (
    TutorSession,
    TutorSessionPlan,
    PedagogicalEvent,
    HintEvent,
)
from app.utils.logger import get_logger

logger = get_logger("services.pedagogical_events")


# ─── Session lifecycle ────────────────────────────────────────────────────────

def create_tutor_session(learner_id: str, section: str) -> str:
    """Creates a TutorSession row; returns its session_id."""
    session_id = str(uuid.uuid4())[:12]
    db = SessionLocal()
    try:
        db.add(TutorSession(
            session_id=session_id,
            learner_id=learner_id,
            section=section,
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create tutor session: {e}")
    finally:
        db.close()
    return session_id


def update_session_state(session_id: str, state: str) -> None:
    """Tracks the last known conversation state; stamps completion."""
    db = SessionLocal()
    try:
        row = db.query(TutorSession).filter(
            TutorSession.session_id == session_id
        ).first()
        if row:
            row.state = state
            if state == "bridge_to_practice" and row.completed_at is None:
                row.completed_at = datetime.now()
            db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to update session state: {e}")
    finally:
        db.close()


# ─── Event recording (called by the tag parser, server-side) ─────────────────

def record_event(
    session_id: str,
    learner_id: str,
    section: str,
    action_type: str,
    criterion_id: str = None,
    framework_id: str = None,
    success: bool = None,
    evidence: dict = None,
) -> str:
    """Records one pedagogical event. Returns event_id."""
    event_id = str(uuid.uuid4())[:12]
    db = SessionLocal()
    try:
        db.add(PedagogicalEvent(
            event_id=event_id,
            session_id=session_id,
            learner_id=learner_id,
            section=section,
            criterion_id=criterion_id,
            framework_id=framework_id,
            action_type=action_type,
            success=None if success is None else (1 if success else 0),
            evidence_json=json.dumps(evidence) if evidence else None,
        ))
        db.commit()
        logger.info(
            f"pedagogical_event session={session_id} action={action_type} "
            f"criterion={criterion_id} framework={framework_id}"
        )
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to record pedagogical event: {e}")
    finally:
        db.close()
    return event_id


def record_hint(
    session_id: str,
    learner_id: str,
    section: str,
    hint_level: int,
    criterion_id: str = None,
    framework_id: str = None,
) -> str:
    """Records one hint event. Returns hint_event_id."""
    hint_event_id = str(uuid.uuid4())[:12]
    db = SessionLocal()
    try:
        db.add(HintEvent(
            hint_event_id=hint_event_id,
            session_id=session_id,
            learner_id=learner_id,
            section=section,
            criterion_id=criterion_id,
            framework_id=framework_id,
            hint_level=hint_level,
        ))
        db.commit()
        logger.info(
            f"hint_given session={session_id} level={hint_level} "
            f"criterion={criterion_id}"
        )
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to record hint event: {e}")
    finally:
        db.close()
    return hint_event_id


def mark_last_hint_self_corrected(
    session_id: str,
    self_corrected: bool
) -> None:
    """
    When the learner attempts after a hint, links the outcome back to
    the most recent unresolved hint in the session.
    """
    db = SessionLocal()
    try:
        row = db.query(HintEvent).filter(
            HintEvent.session_id == session_id,
            HintEvent.self_corrected.is_(None),
        ).order_by(HintEvent.created_at.desc()).first()
        if row:
            row.self_corrected = 1 if self_corrected else 0
            db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to mark hint outcome: {e}")
    finally:
        db.close()


def complete_session_plan(session_id: str, outcome: str) -> None:
    """Stamps the session plan with its final outcome."""
    db = SessionLocal()
    try:
        row = db.query(TutorSessionPlan).filter(
            TutorSessionPlan.session_id == session_id
        ).first()
        if row:
            row.outcome = outcome
            row.completed_at = datetime.now()
            db.commit()
            logger.info(f"exit_criteria session={session_id} outcome={outcome}")
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to complete session plan: {e}")
    finally:
        db.close()


def get_session_plan(session_id: str) -> dict | None:
    """The persisted pedagogy plan for a session, or None."""
    db = SessionLocal()
    try:
        row = db.query(TutorSessionPlan).filter(
            TutorSessionPlan.session_id == session_id
        ).first()
        if not row:
            return None
        return {
            "session_plan_id": row.session_plan_id,
            "section": row.section,
            "target_skill": row.target_skill,
            "target_criterion": row.target_criterion,
            "target_descriptor": row.target_descriptor,
            "current_stage": row.current_stage,
            "dominant_framework": row.dominant_framework,
            "supporting_frameworks": json.loads(row.supporting_frameworks_json or "[]"),
            "support_level": row.support_level,
            "practice_conditions": json.loads(row.practice_conditions_json or "{}"),
            "feedback_priorities": json.loads(row.feedback_priorities_json or "[]"),
            "exit_criteria": json.loads(row.exit_criteria_json or "{}"),
            "outcome": row.outcome,
        }
    finally:
        db.close()


# ─── Evidence queries (used by the Coach and the resolver) ───────────────────

def get_session_events(session_id: str) -> list:
    """All pedagogical events for one session, oldest first."""
    db = SessionLocal()
    try:
        rows = db.query(PedagogicalEvent).filter(
            PedagogicalEvent.session_id == session_id
        ).order_by(PedagogicalEvent.created_at.asc()).all()
        return [
            {
                "event_id": r.event_id,
                "action_type": r.action_type,
                "criterion_id": r.criterion_id,
                "framework_id": r.framework_id,
                "success": None if r.success is None else bool(r.success),
                "evidence": json.loads(r.evidence_json) if r.evidence_json else None,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]
    finally:
        db.close()


def get_session_hints(session_id: str) -> list:
    """All hint events for one session, oldest first."""
    db = SessionLocal()
    try:
        rows = db.query(HintEvent).filter(
            HintEvent.session_id == session_id
        ).order_by(HintEvent.created_at.asc()).all()
        return [
            {
                "hint_event_id": r.hint_event_id,
                "hint_level": r.hint_level,
                "criterion_id": r.criterion_id,
                "self_corrected": None if r.self_corrected is None else bool(r.self_corrected),
                "created_at": str(r.created_at),
            }
            for r in rows
        ]
    finally:
        db.close()


def get_hint_dependency(
    learner_id: str,
    section: str,
    criterion_id: str = None,
    window: int = 10,
) -> dict:
    """
    Hint-dependency metrics: average hint level over the recent
    window, plus trend (recent half vs older half).

    Falling hint-dependence over time is promotion evidence.
    """
    db = SessionLocal()
    try:
        q = db.query(HintEvent).filter(
            HintEvent.learner_id == learner_id,
            HintEvent.section == section,
        )
        if criterion_id:
            q = q.filter(HintEvent.criterion_id == criterion_id)
        rows = q.order_by(HintEvent.created_at.desc()).limit(window).all()
    finally:
        db.close()

    if not rows:
        return {"average_hint_level": 0.0, "trend": "no_data", "hint_count": 0}

    levels = [r.hint_level for r in rows]  # newest first
    avg = sum(levels) / len(levels)

    trend = "stable"
    if len(levels) >= 4:
        half = len(levels) // 2
        recent_avg = sum(levels[:half]) / half
        older_avg = sum(levels[half:]) / (len(levels) - half)
        if recent_avg < older_avg - 0.3:
            trend = "decreasing"
        elif recent_avg > older_avg + 0.3:
            trend = "increasing"

    self_corrections = [r for r in rows if r.self_corrected is not None]
    self_correction_rate = (
        sum(1 for r in self_corrections if r.self_corrected) / len(self_corrections)
        if self_corrections else None
    )

    return {
        "average_hint_level": round(avg, 2),
        "trend": trend,
        "hint_count": len(levels),
        "self_correction_rate": self_correction_rate,
    }


def summarize_session_evidence(session_id: str) -> dict:
    """
    Compact evidence summary of one session — what the Coach reads
    when interpreting a completed Tutor session.
    """
    events = get_session_events(session_id)
    hints = get_session_hints(session_id)

    attempts = [e for e in events if e["action_type"] == "learner_attempted"]
    successes = [e for e in attempts if e["success"]]
    self_corr = [
        e for e in events
        if e["action_type"] in ("self_correction_succeeded", "self_correction_failed")
    ]
    independent = [e for e in events if e["action_type"] == "independent_check_started"]

    return {
        "session_id": session_id,
        "total_events": len(events),
        "learner_attempts": len(attempts),
        "successful_attempts": len(successes),
        "self_corrections_succeeded": sum(
            1 for e in self_corr if e["action_type"] == "self_correction_succeeded"
        ),
        "self_corrections_failed": sum(
            1 for e in self_corr if e["action_type"] == "self_correction_failed"
        ),
        "independent_checks": len(independent),
        "hints_given": len(hints),
        "highest_hint_level": max((h["hint_level"] for h in hints), default=0),
        "average_hint_level": (
            round(sum(h["hint_level"] for h in hints) / len(hints), 2)
            if hints else 0.0
        ),
        "models_shown": sum(1 for e in events if e["action_type"] == "model_shown"),
        "events": events,
    }
