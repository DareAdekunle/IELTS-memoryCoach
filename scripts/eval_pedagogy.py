"""
scripts/eval_pedagogy.py

Offline behaviour evaluation of the Pedagogical Skill Layer
(spec §25.2 checks). Run against recorded sessions — NOT a runtime
gate and NOT a CI unit test, because LLM output checks are heuristic.

Usage (from repo root):
  python scripts/eval_pedagogy.py            # evaluate recent sessions
  python scripts/eval_pedagogy.py <session_id>

Checks per session:
  1. Hints escalate one level at a time (never skip levels upward)
  2. Every hint has a recorded outcome (self_corrected set) — coverage %
  3. An independent check happened before framework completion
  4. Feedback events exist when a plan exists
  5. Session plan has an outcome when the session completed
"""

import sys
sys.path.append('.')

from app.db.database import SessionLocal
from app.db.models import TutorSession
from app.services.pedagogical_event_service import (
    get_session_events, get_session_hints, get_session_plan,
)


def evaluate_session(session_id: str) -> dict:
    events = get_session_events(session_id)
    hints = get_session_hints(session_id)
    plan = get_session_plan(session_id)

    checks = {}

    # 1. Hint escalation — one level at a time (upward)
    escalation_ok = True
    prev = 0
    for h in hints:
        if h["hint_level"] > prev + 1 and prev > 0:
            escalation_ok = False
            break
        prev = max(prev, h["hint_level"])
    checks["hints_escalate_one_level"] = escalation_ok if hints else None

    # 2. Hint outcome coverage
    if hints:
        resolved = sum(1 for h in hints if h["self_corrected"] is not None)
        checks["hint_outcome_coverage"] = round(resolved / len(hints), 2)
    else:
        checks["hint_outcome_coverage"] = None

    # 3. Independent check before completion
    types = [e["action_type"] for e in events]
    if "framework_completed" in types:
        idx = types.index("framework_completed")
        checks["independent_check_before_completion"] = (
            "independent_check_started" in types[:idx]
        )
    else:
        checks["independent_check_before_completion"] = None

    # 4. Feedback recorded when a plan exists
    checks["feedback_recorded"] = (
        ("feedback_given" in types) if plan else None
    )

    # 5. Plan outcome set for completed sessions
    checks["plan_outcome_set"] = (
        bool(plan.get("outcome")) if plan else None
    )

    applicable = [v for v in checks.values() if v is not None]
    passed = [
        v for v in applicable
        if v is True or (isinstance(v, float) and v >= 0.8)
    ]

    return {
        "session_id": session_id,
        "events": len(events),
        "hints": len(hints),
        "has_plan": plan is not None,
        "checks": checks,
        "score": f"{len(passed)}/{len(applicable)}" if applicable else "n/a",
    }


def main():
    if len(sys.argv) > 1:
        session_ids = [sys.argv[1]]
    else:
        db = SessionLocal()
        try:
            rows = db.query(TutorSession).order_by(
                TutorSession.started_at.desc()
            ).limit(20).all()
            session_ids = [r.session_id for r in rows]
        finally:
            db.close()

    if not session_ids:
        print("No tutor sessions recorded yet.")
        return

    print(f"Evaluating {len(session_ids)} session(s)\n")
    for sid in session_ids:
        result = evaluate_session(sid)
        print(f"session {result['session_id']}  "
              f"events={result['events']} hints={result['hints']} "
              f"plan={'yes' if result['has_plan'] else 'no'}  "
              f"score={result['score']}")
        for name, value in result["checks"].items():
            symbol = "—" if value is None else ("✅" if (
                value is True or (isinstance(value, float) and value >= 0.8)
            ) else "❌")
            print(f"    {symbol} {name}: {value}")
        print()


if __name__ == "__main__":
    main()
