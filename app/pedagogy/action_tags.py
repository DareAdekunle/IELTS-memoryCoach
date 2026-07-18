"""
app/pedagogy/action_tags.py

Structured action tags — how the app learns what happened inside
freeform Tutor conversation.

Extends the existing [STATE: xxx] convention. The Tutor emits tags
like:

  [ACTION: hint level=2]
  [ACTION: attempt result=self_corrected]
  [ACTION: model_shown]
  [ACTION: independent_check]
  [ACTION: complete outcome=completed]

The server parses them, strips them from the learner-facing text,
and records pedagogical/hint events. This is the linchpin of the
evidence loop: the Tutor records what happened; the Coach decides
what it means.

Tags are best-effort — a missing tag loses one data point, never
breaks the conversation.
"""

import re

# [ACTION: name key=value key=value]
# Tolerant of model formatting drift: "[ ACTION : hint level = 2 ]"
ACTION_RE = re.compile(
    r'\[\s*ACTION\s*:\s*(\w+)((?:\s+\w+\s*=\s*[\w.\-]+)*)\s*\]',
    re.IGNORECASE
)
PARAM_RE = re.compile(r'(\w+)\s*=\s*([\w.\-]+)')

VALID_ACTIONS = {
    "hint",                # params: level (1-4)
    "attempt",             # params: result (success|failed|self_corrected)
    "model_shown",
    "framework_started",
    "feedback_given",
    "independent_check",
    "complete",            # params: outcome (completed|needs_more_practice|...)
}

ATTEMPT_RESULTS = {"success", "failed", "self_corrected"}
COMPLETE_OUTCOMES = {
    "completed",
    "needs_more_guided_practice",
    "support_should_increase",
    "ready_for_reduced_support",
    "ready_for_timed_condition",
}


def parse_action_tags(text: str) -> tuple:
    """
    Extracts all [ACTION: ...] tags from Tutor output.

    Returns (clean_text, actions) where actions is a list of
    {"action": str, "params": dict}. Unknown action names and
    malformed params are dropped silently (best-effort).
    """
    actions = []

    for match in ACTION_RE.finditer(text):
        name = match.group(1).lower()
        if name not in VALID_ACTIONS:
            continue

        params = dict(PARAM_RE.findall(match.group(2) or ""))

        # Validate + coerce known params
        if name == "hint":
            try:
                level = int(params.get("level", "0"))
            except ValueError:
                level = 0
            if not 1 <= level <= 4:
                continue
            params["level"] = level

        elif name == "attempt":
            if params.get("result") not in ATTEMPT_RESULTS:
                continue

        elif name == "complete":
            if params.get("outcome") not in COMPLETE_OUTCOMES:
                params["outcome"] = "completed"

        actions.append({"action": name, "params": params})

    clean_text = ACTION_RE.sub("", text)
    # Collapse whitespace artifacts left by tag removal
    clean_text = re.sub(r'[ \t]+\n', '\n', clean_text)
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

    return clean_text, actions


TAG_PROTOCOL_PROMPT = """
## ACTION TAG PROTOCOL (invisible to the learner — the app records these)

Emit these tags inline as events happen. They are stripped before display.

  [ACTION: hint level=N]            — you gave a hint. Level 1 = vague nudge,
                                      2 = narrowed focus, 3 = near-answer,
                                      4 = full answer/explanation.
  [ACTION: attempt result=X]        — the learner just attempted something.
                                      X = success | failed | self_corrected
  [ACTION: model_shown]             — you showed a model/example answer.
  [ACTION: feedback_given]          — you delivered a Feedback Triad message.
  [ACTION: independent_check]       — you set an independent (no-help) task.
  [ACTION: complete outcome=X]      — the activity finished.
                                      X = completed | needs_more_guided_practice |
                                      support_should_increase | ready_for_reduced_support

Rules:
- Emit the tag in the SAME message as the event it describes.
- One hint tag per hint, at the exact level you gave.
- Tag the learner's attempt in YOUR reply that responds to it.
- These tags are separate from [STATE: xxx], which you must still emit
  at the end of every reply.
"""
