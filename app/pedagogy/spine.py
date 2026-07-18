"""
app/pedagogy/spine.py

Soft validation of the Shared Pedagogical Spine on Tutor output.

Tiered enforcement (deliberate design decision):
  HARD (code):    plan contents, hint escalation order, condition
                  gates, stage/rank changes — never the model's call.
  SOFT (here):    Feedback Triad structure, priority-count cap —
                  checked heuristically, one regeneration retry,
                  then log-only. Never blocks the conversation.
  PROMPT (trust): elicitation phrasing, tone.

A regex police layer that rejects Tutor replies would make the chat
brittle; these checks nudge, log, and move on.
"""

import re

from app.utils.logger import get_logger

logger = get_logger("pedagogy.spine")

# Signals that a message is "significant feedback" (triad expected)
FEEDBACK_SIGNALS = [
    r'\bfeedback\b', r'\byour (essay|answer|response|paragraph|attempt)\b',
    r'\byou (did|wrote|said|missed|chose)\b', r'\bwell done\b',
    r'\berror', r'\bcorrect', r'\bimprove',
]

GOAL_SIGNALS = [
    r'\bgoal\b', r'\baiming\b', r'\btarget\b', r'\bband \d', r'\bworking toward',
]
CURRENT_SIGNALS = [
    r'\bright now\b', r'\bcurrently\b', r'\byour (current|last|recent)\b',
    r'\bat the moment\b', r'\byou (are|is|were)\b',
]
NEXT_STEP_SIGNALS = [
    r'\bnext step\b', r'\bnext,?\b', r'\btry\b', r'\bnow\b.{0,40}\b(write|correct|find|fix|rewrite|attempt)\b',
    r'\byour turn\b', r'\bcan you\b',
]


def _any(patterns: list, text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_feedback_message(text: str) -> bool:
    """Heuristic: does this reply deliver feedback on learner work?"""
    return len(text) > 200 and _any(FEEDBACK_SIGNALS, text)


def validate_triad(text: str) -> dict:
    """
    Checks the three legs of the Feedback Triad.
    Heuristic — used for a soft retry and observability, never a hard gate.
    """
    legs = {
        "goal": _any(GOAL_SIGNALS, text),
        "current_position": _any(CURRENT_SIGNALS, text),
        "next_step": _any(NEXT_STEP_SIGNALS, text),
    }
    return {
        "passed": all(legs.values()),
        "legs": legs,
        "missing": [k for k, v in legs.items() if not v],
    }


def count_priorities(text: str) -> int:
    """
    Approximates how many distinct improvement priorities a feedback
    message asks for, by counting top-level list items in the reply.
    """
    numbered = re.findall(r'^\s*\d+[.)]\s', text, re.MULTILINE)
    bulleted = re.findall(r'^\s*[-*•]\s', text, re.MULTILINE)
    return max(len(numbered), len(bulleted))


def validate_spine(text: str, max_priorities: int = 3) -> dict:
    """
    Runs all soft spine checks on one Tutor reply.

    Returns {"passed", "is_feedback", "triad", "priority_count",
    "retry_nudge"} — retry_nudge is a corrective instruction usable
    for one regeneration attempt.
    """
    if not is_feedback_message(text):
        return {
            "passed": True,
            "is_feedback": False,
            "triad": None,
            "priority_count": 0,
            "retry_nudge": None,
        }

    triad = validate_triad(text)
    priorities = count_priorities(text)
    too_many = priorities > max_priorities + 2  # tolerance: lists aren't always priorities

    passed = triad["passed"] and not too_many

    nudge = None
    if not passed:
        problems = []
        if not triad["passed"]:
            problems.append(
                "restructure your feedback as a Feedback Triad — state the GOAL "
                "(target band descriptor), the learner's CURRENT position, and "
                "ONE concrete NEXT STEP (missing: "
                + ", ".join(triad["missing"]) + ")"
            )
        if too_many:
            problems.append(
                f"you listed ~{priorities} items — cap feedback at "
                f"{max_priorities} priorities maximum"
            )
        nudge = (
            "Your previous reply violated the teaching rules: "
            + "; ".join(problems)
            + ". Rewrite the reply. Keep the same content intent, same "
            "[STATE:] tag, and same [ACTION:] tags."
        )
        logger.info(f"spine_check_failed missing={triad['missing']} priorities={priorities}")

    return {
        "passed": passed,
        "is_feedback": True,
        "triad": triad,
        "priority_count": priorities,
        "retry_nudge": nudge,
    }
