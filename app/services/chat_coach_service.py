import os
import sys
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import call_qwen
from app.services.memory_service import build_chat_coach_context

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

VALID_STATES = {"introduction", "explaining", "drilling", "bridge_to_practice"}


def load_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def format_context_brief(context: dict) -> str:
    """
    Turns the context dict from build_chat_coach_context() into a
    readable text block for the system prompt.
    """
    weakest = context["weakest_skill"]
    skill_def = context["skill_definition"]

    lines = [
        f"Weakest skill: {skill_def['skill_name']} "
        f"(category: {skill_def['category_name']})",
        f"Skill description: {skill_def['description']}",
        f"Current rank: {weakest['current_rank']}/5 "
        f"({weakest['rank_name']})",
        f"What this current rank looks like: "
        f"{context['current_rank_text']}",
        f"What the NEXT rank looks like (the goal): "
        f"{context['next_rank_text']}",
    ]

    if context.get("evidence_memory"):
        lines.append(
            f"\nSpecific evidence from their writing: "
            f"{context['evidence_memory']['memory_text']}"
        )

    if context.get("recent_essay"):
        essay = context["recent_essay"]
        # Truncate to keep the prompt manageable -- we don't need
        # the full essay, just enough for the coach to reference it
        excerpt = essay["essay"][:600]
        lines.append(
            f"\nTheir most recent essay was written for this prompt: "
            f"\"{essay['prompt'][:150]}...\"\n"
            f"Excerpt of what they wrote: \"{excerpt}...\""
        )

    return "\n".join(lines)


def parse_state_tag(raw_response: str) -> tuple:
    """
    Extracts the [STATE: xxx] tag from the end of a response and
    returns (clean_text, state).

    If no valid tag is found, defaults state to "explaining" --
    a safe middle-ground state that doesn't trigger the bridge
    button prematurely and doesn't restart the introduction
    unnecessarily.
    """
    match = re.search(r'\[STATE:\s*(\w+)\]\s*$', raw_response.strip())

    if not match:
        return raw_response.strip(), "explaining"

    state = match.group(1).strip()
    clean_text = raw_response[:match.start()].strip()

    if state not in VALID_STATES:
        state = "explaining"

    return clean_text, state


def start_chat_session(learner_id: str, section: str = "Writing") -> dict:
    """
    Builds the opening message for a new Chat Coach session.

    Returns a dict with:
    - message: the coach's opening text (tag already stripped)
    - state: the current state ("introduction" or similar)
    - has_history: whether this learner has skill evidence yet
    - context: the raw context dict (needed for later turns)
    """
    context = build_chat_coach_context(learner_id, section)

    if not context["has_history"]:
        template = load_prompt_template("chat_coach_welcome_prompt.txt")
        raw_response = call_qwen(prompt=template, temperature=0.6)
        clean_text, state = parse_state_tag(raw_response)

        return {
            "message": clean_text,
            "state": state,
            "has_history": False,
            "context": context
        }

    context_brief = format_context_brief(context)
    template = load_prompt_template("chat_coach_prompt.txt")
    system_prompt = template.format(context_brief=context_brief)

    # The first turn just needs the coach to open -- no learner
    # message yet, so we prompt it to begin the introduction
    opening_instruction = (
        "Begin the conversation now by opening with the "
        "INTRODUCTION step as described in your instructions."
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
        "context": context,
        "system_prompt": system_prompt
    }


def continue_chat_session(
    system_prompt: str,
    conversation_history: list,
    learner_message: str
) -> dict:
    """
    Continues an existing chat session with a new learner message.

    conversation_history is a list of {"role": ..., "content": ...}
    dicts representing the conversation SO FAR (not including the
    new learner_message, which gets appended here).

    Returns a dict with:
    - message: the coach's reply (tag stripped)
    - state: the new state after this turn
    """
    messages = conversation_history + [
        {"role": "user", "content": learner_message}
    ]

    # call_qwen only accepts a single prompt + optional system_message,
    # so we build the full message list manually here using the same
    # underlying client setup as qwen_service, rather than forcing
    # multi-turn history through a single-string prompt
    from app.services.qwen_service import client, QWEN_MODEL

    full_messages = [{"role": "system", "content": system_prompt}] + messages

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

