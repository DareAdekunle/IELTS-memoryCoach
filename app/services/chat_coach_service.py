"""
app/services/chat_coach_service.py

Specialist AI tutor service supporting all four IELTS sections.

Each section has a dedicated tutor with section-specific:
  - System prompt (specialist knowledge, teaching strategies)
  - Skill taxonomy (for context building)
  - Memory context (from learner's actual practice history)

The tutor uses the MCP-style context builder to fetch the
learner's weakest skill and relevant memories before opening
the session — ensuring every conversation is grounded in
real evidence from the learner's own practice.
"""

import os
import sys
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import call_qwen, client, QWEN_MODEL
from app.services.memory_service import build_chat_coach_context

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

VALID_STATES = {"introduction", "explaining", "drilling", "bridge_to_practice"}

# ─── Section → prompt file mapping ───────────────────────────────────────────

TUTOR_PROMPTS = {
    "Writing":   "writing_tutor_prompt.txt",
    "Reading":   "reading_tutor_prompt.txt",
    "Speaking":  "speaking_tutor_prompt.txt",
    "Listening": "listening_tutor_prompt.txt",
}

SECTION_LABELS = {
    "Writing":   "IELTS Writing",
    "Reading":   "IELTS Reading",
    "Speaking":  "IELTS Speaking",
    "Listening": "IELTS Listening",
}

# ─── Welcome prompt (used when learner has no history) ───────────────────────

WELCOME_PROMPT_TEMPLATE = """You are an expert {section_label} tutor.

The learner has not yet submitted enough {section_label} practice to have a 
personalised skill profile. Warmly welcome them and encourage them to complete 
a {section_label} practice session first so you can personalise your coaching.

Keep this short, warm and encouraging — 2-3 sentences maximum.

After your reply, on its own line, include exactly:
[STATE: introduction]
"""


def load_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def parse_state_tag(raw_response: str) -> tuple:
    """
    Extracts the [STATE: xxx] tag from the end of a response.
    Returns (clean_text, state).
    Defaults to "explaining" if tag is missing or invalid.
    """
    match = re.search(r'\[STATE:\s*(\w+)\]\s*$', raw_response.strip())

    if not match:
        return raw_response.strip(), "explaining"

    state = match.group(1).strip()
    clean_text = raw_response[:match.start()].strip()

    if state not in VALID_STATES:
        state = "explaining"

    return clean_text, state


def format_context_brief(context: dict, section: str) -> str:
    """
    Formats the learner context into a readable text block
    for injection into the specialist tutor system prompt.
    """
    weakest = context.get("weakest_skill")
    skill_def = context.get("skill_definition")

    if not weakest or not skill_def:
        return f"No {section} skill data available yet for this learner."

    lines = [
        f"Section: {section}",
        f"Weakest skill: {skill_def['skill_name']} "
        f"(category: {skill_def['category_name']})",
        f"Skill description: {skill_def['description']}",
        f"Current rank: {weakest['current_rank']}/5 "
        f"({weakest['rank_name']})",
        f"What this rank looks like: {context.get('current_rank_text', '')}",
        f"What the next rank looks like (the goal): "
        f"{context.get('next_rank_text', '')}",
    ]

    if context.get("evidence_memory"):
        lines.append(
            f"\nSpecific evidence from their {section} practice: "
            f"{context['evidence_memory']['memory_text']}"
        )

    if context.get("recent_essay"):
        essay = context["recent_essay"]
        excerpt = essay["essay"][:500]
        lines.append(
            f"\nTheir most recent {section} attempt was for: "
            f"\"{essay['prompt'][:150]}...\"\n"
            f"Excerpt: \"{excerpt}...\""
        )

    return "\n".join(lines)


def start_chat_session(
    learner_id: str,
    section: str = "Writing"
) -> dict:
    """
    Starts a new specialist tutor session for the given section.

    Selects the appropriate specialist tutor prompt, builds
    personalised context from the learner's practice history,
    and generates the tutor's opening message.

    Returns:
        message:       The tutor's opening text (state tag stripped)
        state:         Current state ("introduction" etc.)
        has_history:   Whether this learner has practice data
        section:       Which section this session is for
        system_prompt: Full system prompt for subsequent turns
    """
    # Validate section
    if section not in TUTOR_PROMPTS:
        section = "Writing"

    # Build learner context
    context = build_chat_coach_context(learner_id, section)

    # No history — use welcome message
    if not context["has_history"]:
        welcome = WELCOME_PROMPT_TEMPLATE.format(
            section_label=SECTION_LABELS[section]
        )
        raw_response = call_qwen(prompt=welcome, temperature=0.6)
        clean_text, state = parse_state_tag(raw_response)

        return {
            "message": clean_text,
            "state": state,
            "has_history": False,
            "section": section,
            "system_prompt": ""
        }

    # Build specialist system prompt
    context_brief = format_context_brief(context, section)
    template = load_prompt_template(TUTOR_PROMPTS[section])
    system_prompt = template.format(context_brief=context_brief)

    # Generate opening message
    opening_instruction = (
        f"Begin the {SECTION_LABELS[section]} tutoring session now "
        f"with the INTRODUCTION step as described in your instructions."
    )

    raw_response = call_qwen(
        prompt=opening_instruction,
        system_message=system_prompt,
        temperature=0.6
    )
    clean_text, state = parse_state_tag(raw_response)

    return {
        "message": clean_text,
        "state": state,
        "has_history": True,
        "section": section,
        "system_prompt": system_prompt,
        "context": context
    }


def continue_chat_session(
    system_prompt: str,
    conversation_history: list,
    learner_message: str
) -> dict:
    """
    Continues an existing tutor session with a new learner message.

    conversation_history is the full conversation so far, NOT
    including the new learner_message (which is appended here).

    Returns:
        message: The tutor's reply (state tag stripped)
        state:   The new conversation state
    """
    messages = conversation_history + [
        {"role": "user", "content": learner_message}
    ]

    full_messages = [
        {"role": "system", "content": system_prompt}
    ] + messages

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=full_messages,
        temperature=0.6
    )
    raw_response = response.choices[0].message.content
    clean_text, state = parse_state_tag(raw_response)

    return {
        "message": clean_text,
        "state": state
    }
