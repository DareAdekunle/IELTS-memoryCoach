"""
app/mcp/memory_server.py — Qonda IELTS MCP Server

Exposes the Qonda IELTS learner memory and skill ranking system
as an MCP (Model Context Protocol) server.

This means any MCP-compatible AI agent — Claude, a Qwen agent,
a school's tutoring bot, or a custom dashboard — can query a
learner's coaching history without direct database access.

Tools exposed:
  get_learner_weaknesses    — active weakness memories for a learner
  get_learner_strengths     — active strength memories for a learner
  get_skill_ranks           — all 13 writing skill rank levels
  get_weakest_skill         — single weakest skill for targeting
  get_recent_attempts       — recent attempt history by section
  get_memory_stats          — memory profile statistics
  get_coaching_context      — full context bundle for AI tutoring agents

Usage:
  Run standalone:
    python app/mcp/memory_server.py

  Or mount into FastAPI (see api/main.py):
    from app.mcp.memory_server import mcp
    app.mount("/mcp", mcp.get_asgi_app())
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP
from app.db.database import SessionLocal
from app.db.models import LearnerMemory, PracticeAttempt, LearnerSkillRank, Learner
from api.auth.models import User
from app.services.memory_service import (
    get_relevant_memories,
    get_all_memories,
    get_memory_stats,
    get_weakest_skill,
    get_all_skill_ranks,
    get_skill_progress_summary
)
from app.services.skill_taxonomy_service import get_skill_by_id, get_rank_name

# ─── MCP Server definition ────────────────────────────────────────────────────

mcp = FastMCP(
    name="Qonda IELTS",
    instructions=(
        "This server exposes learner coaching data from Qonda IELTS — an AI-powered "
        "IELTS preparation platform with persistent memory and skill tracking.\n\n"
        "IMPORTANT: All tools require a learner_id (a UUID). "
        "If the user has not provided their learner_id, call find_learner(email) first "
        "using the email address they provide. Ask them for their email if you don't have it.\n\n"
        "For a full learner overview, always start with get_coaching_context — it combines "
        "weaknesses, strengths, skill ranks, and memory stats in a single call.\n\n"
        "For scheduling: use get_study_schedule to check the current schedule, "
        "schedule_study_sessions to create or change it, add_one_off_session for a "
        "one-time extra session, and cancel_study_schedule to remove it entirely."
    )
)


# ─── Tool 0: Find learner by email ───────────────────────────────────────────

@mcp.tool()
def find_learner(email: str) -> dict:
    """
    Look up a learner's ID and profile using their email address.

    Call this first whenever the user hasn't provided a learner_id.
    Ask the user for their email address if you don't already have it.

    Args:
        email: The learner's email address (e.g. "student@example.com")

    Returns:
        A dict with learner_id, name, target_score, test_date, and current_focus
        if found. Returns {"found": false, "message": "..."} if no account exists.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user or not user.learner_id:
            return {
                "found": False,
                "message": f"No Qonda learner profile found for {email}. "
                           "They may need to register at ielts.qonda.xyz first."
            }
        learner = db.query(Learner).filter(Learner.learner_id == user.learner_id).first()
        if not learner:
            return {
                "found": False,
                "message": "User account exists but learner profile not yet created. "
                           "Ask them to complete onboarding at ielts.qonda.xyz/onboarding."
            }
        return {
            "found": True,
            "learner_id": learner.learner_id,
            "name": learner.name,
            "target_score": learner.target_score,
            "test_date": str(learner.test_date) if learner.test_date else None,
            "current_focus": learner.current_focus,
        }
    finally:
        db.close()


# ─── Tool 1: Get learner weaknesses ───────────────────────────────────────────

@mcp.tool()
def get_learner_weaknesses(
    learner_id: str,
    section: str = "Writing",
    limit: int = 5
) -> dict:
    """
    Returns the most relevant active weakness memories for a learner
    in a given IELTS section.

    These are specific, evidence-based observations extracted by the
    AI coach after each practice attempt — not generic feedback.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section — Writing, Reading, Speaking, Listening
        limit:      Maximum number of memories to return (default 5)

    Returns:
        A dict with 'weaknesses' list, each containing:
        - skill: the skill area (e.g. "Thesis Clarity")
        - memory_text: specific observation about the learner
        - confidence: how confident the coach is (0.0-1.0)
        - evidence_count: how many attempts support this memory
    """
    memories = get_relevant_memories(
        learner_id=learner_id,
        section=section,
        limit=limit
    )

    weaknesses = [
        {
            "skill": m["skill"],
            "memory_text": m["memory_text"],
            "confidence": m["confidence"],
            "evidence_count": m["evidence_count"]
        }
        for m in memories
        if m["memory_type"] == "weakness"
    ]

    return {
        "learner_id": learner_id,
        "section": section,
        "weaknesses": weaknesses,
        "count": len(weaknesses)
    }


# ─── Tool 2: Get learner strengths ────────────────────────────────────────────

@mcp.tool()
def get_learner_strengths(
    learner_id: str,
    section: str = "Writing",
    limit: int = 5
) -> dict:
    """
    Returns the most relevant active strength memories for a learner.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section — Writing, Reading, Speaking, Listening
        limit:      Maximum number of memories to return (default 5)

    Returns:
        A dict with 'strengths' list, each containing skill,
        memory_text, confidence, and evidence_count.
    """
    memories = get_relevant_memories(
        learner_id=learner_id,
        section=section,
        limit=limit
    )

    strengths = [
        {
            "skill": m["skill"],
            "memory_text": m["memory_text"],
            "confidence": m["confidence"],
            "evidence_count": m["evidence_count"]
        }
        for m in memories
        if m["memory_type"] == "strength"
    ]

    return {
        "learner_id": learner_id,
        "section": section,
        "strengths": strengths,
        "count": len(strengths)
    }


# ─── Tool 3: Get skill ranks ───────────────────────────────────────────────────

@mcp.tool()
def get_skill_ranks(
    learner_id: str,
    section: str = "Writing"
) -> dict:
    """
    Returns the learner's mastery rank on all 13 IELTS Writing
    sub-skills derived from the official Band Descriptors.

    Ranks range from 1 (Beginner) to 5 (Advanced) and are updated
    deterministically after each essay submission using a clean-streak
    rule engine — 3 consecutive demonstrated strengths = rank up.

    Args:
        learner_id: The learner's unique ID
        section:    Currently only "Writing" has a full taxonomy

    Returns:
        A dict with 'skills' list grouped by category, each containing:
        - skill_id, skill_name, category_name
        - current_rank (1-5), rank_name (Beginner→Advanced)
        - clean_streak: consecutive strengths toward next rank
        - total_evidence: total times this skill was assessed
    """
    all_ranks = get_all_skill_ranks(learner_id, section)
    summary = get_skill_progress_summary(learner_id, section)

    return {
        "learner_id": learner_id,
        "section": section,
        "skills": all_ranks,
        "summary": {
            "total_skills": summary["total_skills"],
            "average_rank": summary["average_rank"],
            "skills_at_advanced": summary["skills_at_max"],
            "skills_untouched": summary["skills_untouched"]
        }
    }


# ─── Tool 4: Get weakest skill ────────────────────────────────────────────────

@mcp.tool()
def get_weakest_skill_for_learner(learner_id: str, section: str = "Writing") -> dict:
    """
    Identifies the single skill most in need of attention for a learner.

    Priority order:
    1. Lowest current rank (rank 1 before rank 3)
    2. Among tied ranks: lowest total evidence (least known about)
    3. Among tied evidence: most recent demonstrated_weakness

    This is the same logic used by the Chat Coach to decide which
    skill to focus a tutoring session on.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section

    Returns:
        A dict with the weakest skill's full details including
        rank definitions for current and next level — useful for
        generating targeted teaching content.
    """
    weakest = get_weakest_skill(learner_id, section)

    if not weakest:
        return {
            "learner_id": learner_id,
            "has_data": False,
            "message": "No skill data yet — learner needs to submit essays first"
        }

    skill_def = get_skill_by_id(weakest["skill_id"], section)
    current_rank = weakest["current_rank"]
    next_rank = min(current_rank + 1, 5)

    current_rank_text = ""
    next_rank_text = ""
    if skill_def and "ranks" in skill_def:
        current_rank_text = skill_def["ranks"].get(str(current_rank), "")
        next_rank_text = skill_def["ranks"].get(str(next_rank), "")

    return {
        "learner_id": learner_id,
        "has_data": True,
        "skill_id": weakest["skill_id"],
        "skill_name": weakest["skill_name"],
        "category_name": weakest["category_name"],
        "current_rank": current_rank,
        "rank_name": get_rank_name(current_rank),
        "clean_streak": weakest["clean_streak"],
        "total_evidence": weakest["total_evidence"],
        "current_rank_definition": current_rank_text,
        "next_rank_definition": next_rank_text,
        "sessions_to_rank_up": max(0, 3 - weakest["clean_streak"])
    }


# ─── Tool 5: Get recent attempts ──────────────────────────────────────────────

@mcp.tool()
def get_recent_attempts(
    learner_id: str,
    section: str = "Writing",
    limit: int = 5
) -> dict:
    """
    Returns the learner's most recent practice attempts in a section.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section — Writing, Reading, Speaking, Listening
        limit:      Number of attempts to return (default 5, max 20)

    Returns:
        A dict with 'attempts' list, each containing:
        - attempt_id, section, task_type
        - prompt: the question/task the learner responded to
        - score_summary: key scores from the attempt
        - created_at: timestamp
    """
    limit = min(limit, 20)

    db = SessionLocal()
    try:
        attempts = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == learner_id,
            PracticeAttempt.section == section
        ).order_by(
            PracticeAttempt.created_at.desc()
        ).limit(limit).all()

        result = []
        for a in attempts:
            score_summary = {}
            if a.score_json:
                import json
                try:
                    score_data = json.loads(a.score_json) if isinstance(
                        a.score_json, str
                    ) else a.score_json
                    score_summary = score_data.get("scores", {})
                except Exception:
                    pass

            result.append({
                "attempt_id": a.attempt_id,
                "section": a.section,
                "task_type": a.task_type,
                "prompt": a.prompt[:200] + "..." if len(
                    a.prompt or ""
                ) > 200 else a.prompt,
                "score_summary": score_summary,
                "created_at": str(a.created_at)
            })

        return {
            "learner_id": learner_id,
            "section": section,
            "attempts": result,
            "count": len(result)
        }

    finally:
        db.close()


# ─── Tool 6: Get memory stats ─────────────────────────────────────────────────

@mcp.tool()
def get_learner_memory_stats(learner_id: str) -> dict:
    """
    Returns a statistical summary of a learner's memory profile.

    Args:
        learner_id: The learner's unique ID

    Returns:
        A dict with counts of active/archived memories, average
        confidence, and breakdown by memory type (weakness/strength).
    """
    stats = get_memory_stats(learner_id)
    return {
        "learner_id": learner_id,
        **stats
    }


# ─── Tool 7: Get full coaching context ───────────────────────────────────────

@mcp.tool()
def get_coaching_context(
    learner_id: str,
    section: str = "Writing"
) -> dict:
    """
    Start here. Returns a complete coaching context bundle for a learner.

    Call this before generating any personalised content, advice, or practice
    for a learner. It combines weaknesses, strengths, skill ranks, weakest
    skill, and memory stats into a single call — faster than calling each
    tool separately.

    Args:
        learner_id: The learner's unique ID (use find_learner to look this up)
        section:    IELTS section to focus on (default: Writing)

    Returns:
        A comprehensive dict with has_history, weakest_skill, top_weaknesses,
        top_strengths, skill_progress summary, and memory_profile stats.
        Use has_history to detect a new learner with no attempts yet.
    """
    weaknesses = get_learner_weaknesses(learner_id, section, limit=3)
    strengths = get_learner_strengths(learner_id, section, limit=3)
    weakest = get_weakest_skill_for_learner(learner_id, section)
    skill_summary = get_skill_progress_summary(learner_id, section)
    stats = get_memory_stats(learner_id)

    has_history = (
        weakest.get("has_data", False) or
        len(weaknesses.get("weaknesses", [])) > 0
    )

    return {
        "learner_id": learner_id,
        "section": section,
        "has_history": has_history,
        "weakest_skill": weakest if has_history else None,
        "top_weaknesses": weaknesses.get("weaknesses", []),
        "top_strengths": strengths.get("strengths", []),
        "skill_progress": {
            "average_rank": skill_summary.get("average_rank", 0),
            "skills_at_advanced": skill_summary.get("skills_at_max", 0),
            "total_skills": skill_summary.get("total_skills", 0)
        },
        "memory_profile": {
            "active_memories": stats.get("active_count", 0),
            "archived_memories": stats.get("archived_count", 0),
            "avg_confidence": stats.get("avg_confidence", 0)
        }
    }


# ─── Study Schedule Tools ─────────────────────────────────────────────────────

@mcp.tool()
def schedule_study_sessions(
    learner_id: str,
    days: list,
    study_time: str,
    duration_minutes: int = 30,
    timezone: str = "UTC",
) -> dict:
    """
    Set up recurring study sessions for a learner.

    Creates or replaces the learner's study schedule. If the learner already
    has Google Calendar connected, also creates recurring calendar events.

    Args:
        learner_id:        The learner's ID.
        days:              Days to study — e.g. ["Mon", "Wed", "Fri"].
                           Must be exact 3-letter capitalised abbreviations:
                           Mon, Tue, Wed, Thu, Fri, Sat, Sun.
                           Do NOT use full names (Monday) or lowercase (mon).
        study_time:        Time in HH:MM 24-hour format — e.g. "07:00".
        duration_minutes:  Session length. Must be 15, 30, 45 or 60.
        timezone:          IANA timezone — e.g. "Africa/Lagos", "Asia/Manila".

    Returns a dict with the saved schedule details.
    """
    from app.services import schedule_service, calendar_service
    import json

    schedule = schedule_service.create_or_update_schedule(
        learner_id=learner_id,
        days=days,
        study_time=study_time,
        duration_minutes=duration_minutes,
        timezone=timezone,
    )

    # If learner already has Google Calendar connected, create events now
    raw = schedule_service.get_schedule_raw(learner_id)
    if raw and raw.google_refresh_token:
        try:
            test_date     = schedule_service.get_learner_test_date(learner_id)
            weakest_skill = schedule_service.get_weakest_skill_label(learner_id)
            learner_name  = schedule_service.get_learner_name(learner_id)

            # Delete old events if any
            if raw.google_calendar_event_id:
                calendar_service.delete_study_events(
                    raw.google_refresh_token, raw.google_calendar_event_id
                )

            event_id = calendar_service.create_study_events(
                refresh_token    = raw.google_refresh_token,
                days             = days,
                study_time       = study_time,
                duration_minutes = duration_minutes,
                timezone         = timezone,
                test_date        = test_date,
                weakest_skill    = weakest_skill,
                learner_name     = learner_name,
            )
            schedule_service.attach_google_calendar(
                learner_id    = learner_id,
                refresh_token = raw.google_refresh_token,
                event_id      = event_id,
                google_email  = raw.google_email,
            )
            schedule["calendar_updated"] = True
        except Exception as e:
            schedule["calendar_updated"] = False
            schedule["calendar_error"]   = str(e)

    return schedule


@mcp.tool()
def get_study_schedule(learner_id: str) -> dict:
    """
    Get a learner's current study schedule.

    Returns their study days, time, duration, timezone, and whether they
    have Google Calendar connected. Returns {"has_schedule": false} if none.

    Args:
        learner_id: The learner's ID.
    """
    from app.services import schedule_service
    schedule = schedule_service.get_schedule(learner_id)
    if not schedule:
        return {"has_schedule": False}
    return {"has_schedule": True, **schedule}


@mcp.tool()
def add_one_off_session(
    learner_id: str,
    date_iso: str,
    study_time: str,
    duration_minutes: int = 30,
) -> dict:
    """
    Add a one-off study session on a specific date.

    If the learner has Google Calendar connected, creates a single calendar
    event on that date. Otherwise records the intent without a calendar event.

    Args:
        learner_id:        The learner's ID.
        date_iso:          Date in YYYY-MM-DD format — e.g. "2026-08-15".
        study_time:        Time in HH:MM 24-hour format — e.g. "18:00".
        duration_minutes:  Session length in minutes.
    """
    from app.services import schedule_service, calendar_service
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    raw = schedule_service.get_schedule_raw(learner_id)
    tz_name = raw.timezone if raw else "UTC"

    if not raw or not raw.google_refresh_token:
        return {
            "scheduled": False,
            "reason": "No Google Calendar connected. Ask the learner to connect via the app.",
            "suggested_time": f"{date_iso} {study_time} {tz_name}",
        }

    try:
        import googleapiclient.discovery as gd
        creds   = calendar_service._build_creds(raw.google_refresh_token)
        service = gd.build("calendar", "v3", credentials=creds)

        tz       = ZoneInfo(tz_name)
        hour, minute = map(int, study_time.split(":"))
        start_dt = datetime.strptime(date_iso, "%Y-%m-%d").replace(
            hour=hour, minute=minute, tzinfo=tz
        )
        end_dt   = start_dt + timedelta(minutes=duration_minutes)

        weakest_skill = schedule_service.get_weakest_skill_label(learner_id)
        learner_name  = schedule_service.get_learner_name(learner_id)
        skill_line    = f"\n\nSession focus: {weakest_skill}" if weakest_skill else ""

        event = {
            "summary":     f"Qonda IELTS — {duration_minutes} min practice",
            "description": (
                f"One-off study session for {learner_name}.{skill_line}\n\n"
                f"Open Qonda: https://ielts.qonda.xyz\n\n"
                f"Qonda — Grasp English. Retain for life."
            ),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_name},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": tz_name},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email",  "minutes": 60},
                    {"method": "popup",  "minutes": 10},
                ],
            },
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return {
            "scheduled":  True,
            "event_id":   created["id"],
            "start":      start_dt.isoformat(),
            "duration":   duration_minutes,
            "calendar":   raw.google_email,
        }
    except Exception as e:
        return {"scheduled": False, "error": str(e)}


@mcp.tool()
def cancel_study_schedule(learner_id: str) -> dict:
    """
    Cancel a learner's study schedule and remove all future calendar events.

    Args:
        learner_id: The learner's ID.
    """
    from app.services import schedule_service, calendar_service

    raw = schedule_service.get_schedule_raw(learner_id)
    if not raw:
        return {"cancelled": False, "reason": "No active schedule found"}

    if raw.google_refresh_token and raw.google_calendar_event_id:
        calendar_service.delete_study_events(
            raw.google_refresh_token, raw.google_calendar_event_id
        )

    schedule_service.cancel_schedule(learner_id)
    return {"cancelled": True, "calendar_events_deleted": bool(raw.google_calendar_event_id)}


# ─── Run standalone ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Qonda IELTS MCP Server...")
    print("Tools available:")
    print("  - find_learner                  ← start here (email → learner_id)")
    print("  - get_coaching_context          ← full learner overview in one call")
    print("  - get_learner_weaknesses")
    print("  - get_learner_strengths")
    print("  - get_skill_ranks")
    print("  - get_weakest_skill_for_learner")
    print("  - get_recent_attempts")
    print("  - get_learner_memory_stats")
    print("  - get_study_schedule")
    print("  - schedule_study_sessions")
    print("  - add_one_off_session")
    print("  - cancel_study_schedule")
    mcp.run()
