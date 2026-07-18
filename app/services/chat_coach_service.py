"""
app/services/chat_coach_service.py

Specialist AI Tutor service — upgraded to a true agent loop.

The Tutor is now a tool-calling agent that can query live learner
data mid-conversation rather than relying solely on static context
injected at session start.

Architecture:
  TUTOR AGENT (read-only tools)
    get_coaching_context   — full context bundle
    get_learner_weaknesses — live weakness memories
    get_recent_attempts    — actual learner work to reference
    get_skill_ranks        — progress check during drilling

  Coach/Tutor boundary:
    Tutor READS learner data → personalises teaching
    Coach WRITES learner data → updates ranks and memories
    Tutor never calls submit_classification, write_memory, update_memory

When the Tutor reaches bridge_to_practice, extract_chat_memories()
is called to capture what was observed during drilling — these
micro-memories feed back into the Coach's evidence base.
"""

import os
import sys
import re
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import client, QWEN_MODEL
from app.services.memory_service import (
    build_chat_coach_context,
    extract_chat_memories
)
from app.services.agent_tools import (
    TUTOR_TOOL_SCHEMAS,
    execute_tutor_tool
)
from app.services.pedagogical_event_service import (
    create_tutor_session,
    update_session_state,
    get_session_plan,
    record_event,
    record_hint,
    mark_last_hint_self_corrected,
    complete_session_plan,
)
from app.pedagogy.planner import create_session_plan, format_plan_block
from app.pedagogy.action_tags import parse_action_tags, TAG_PROTOCOL_PROMPT
from app.pedagogy.spine import validate_spine
from app.utils.logger import get_logger

logger = get_logger("services.chat_coach")

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
    # Tolerant of model formatting drift: "[ STATE : drilling ]",
    # and of the tag not being the last thing in the reply.
    matches = list(re.finditer(
        r'\[\s*STATE\s*:\s*(\w+)\s*\]', raw_response, re.IGNORECASE
    ))

    if not matches:
        return raw_response.strip(), "explaining"

    match = matches[-1]

    state = match.group(1).strip().lower()

    # Remove every state tag occurrence (not truncate) so any
    # [ACTION:] tags emitted after the state tag survive for parsing
    clean_text = re.sub(
        r'\[\s*STATE\s*:\s*\w+\s*\]', '', raw_response, flags=re.IGNORECASE
    ).strip()

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

    Builds learner context from practice history and generates
    the tutor's opening message.

    Returns:
        message:       The tutor's opening text (state tag stripped)
        state:         Current state
        has_history:   Whether this learner has practice data
        section:       Which section this session is for
        system_prompt: Full system prompt for subsequent turns
        learner_id:    Passed through for agent loop turns
    """
    if section not in TUTOR_PROMPTS:
        section = "Writing"

    context = build_chat_coach_context(learner_id, section)

    # No history — welcome message only
    if not context["has_history"]:
        welcome = WELCOME_PROMPT_TEMPLATE.format(
            section_label=SECTION_LABELS[section]
        )
        response = client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[{"role": "user", "content": welcome}],
            temperature=0.6
        )
        raw = response.choices[0].message.content
        clean_text, state = parse_state_tag(raw)

        return {
            "message": clean_text,
            "state": state,
            "has_history": False,
            "section": section,
            "system_prompt": "",
            "learner_id": learner_id,
            "session_id": None,
            "pedagogy": None
        }

    # ── Pedagogical Skill Layer ──────────────────────────────────────
    # Server-side session identity + deterministic teaching plan.
    # Python selects the teaching method; Qwen delivers the teaching.
    session_id = create_tutor_session(learner_id, section)
    plan = None
    try:
        plan = create_session_plan(learner_id, section, session_id)
    except Exception as e:
        logger.warning(f"Pedagogy plan creation failed (non-blocking): {e}")

    # Build specialist system prompt
    context_brief = format_context_brief(context, section)
    template = load_prompt_template(TUTOR_PROMPTS[section])
    system_prompt = template.format(context_brief=context_brief)

    # Inject the structured teaching plan (Backward Design anchor,
    # dominant framework procedure, support level, exit criteria)
    if plan:
        system_prompt += "\n" + format_plan_block(plan)

    # Action tag protocol — how the app records hints/attempts
    system_prompt += "\n" + TAG_PROTOCOL_PROMPT

    # Append tool awareness to system prompt
    system_prompt += (
        "\n\n## Your Tools\n"
        "You have access to live learner data tools. Use them when you need "
        "to reference specific evidence mid-conversation:\n"
        "- get_learner_weaknesses: fetch current weakness memories\n"
        "- get_recent_attempts: pull actual learner work to quote\n"
        "- get_skill_ranks: check progress and tell learner how close they "
        "are to ranking up\n"
        "- get_coaching_context: full refresh if you need a complete picture\n"
        "- get_pedagogical_context: criterion stages, support levels and "
        "hint dependency for this learner\n"
        "- get_current_session_plan: re-read this session's teaching plan\n\n"
        "Always include [STATE: xxx] at the end of every response."
    )

    opening_instruction = (
        f"Begin the {SECTION_LABELS[section]} tutoring session now "
        f"with the INTRODUCTION step as described in your instructions."
    )

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": opening_instruction}
        ],
        tools=TUTOR_TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=0.6
    )

    # Handle tool calls at session start (unlikely but possible)
    message = response.choices[0].message
    final_content = message.content or ""

    if message.tool_calls:
        # Execute any tool calls and get final response
        final_content = _resolve_tool_calls(
            system_prompt=system_prompt,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": opening_instruction},
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                }
            ],
            tool_calls=message.tool_calls,
            learner_id=learner_id
        )

    clean_text, state = parse_state_tag(final_content)
    clean_text, actions = parse_action_tags(clean_text)
    _record_actions(actions, session_id, learner_id, section)
    update_session_state(session_id, state)

    return {
        "message": clean_text,
        "state": state,
        "has_history": True,
        "section": section,
        "system_prompt": system_prompt,
        "learner_id": learner_id,
        "context": context,
        "session_id": session_id,
        "pedagogy": plan.to_dict() if plan else None
    }


def continue_chat_session(
    system_prompt: str,
    conversation_history: list,
    learner_message: str,
    learner_id: str = None,
    section: str = "Writing",
    session_id: str = None
) -> dict:
    """
    Continues an existing tutor session with a new learner message.

    The Tutor is now a tool-calling agent — it can query live learner
    data mid-conversation when it needs to reference specific evidence.

    Pedagogical layer per turn:
      1. [ACTION:] tags are parsed from the reply and recorded as
         pedagogical/hint events (the Tutor records what happened).
      2. Soft spine validation (Feedback Triad, priority cap) with
         one regeneration retry — then log-only.
      3. At bridge_to_practice: memories are extracted AND the session
         is marked complete so the Coach can interpret the evidence.

    Returns:
        message:            The tutor's reply (state tag stripped)
        state:              The new conversation state
        memories_extracted: Number of memories saved (0 if not triggered)
        tools_called:       Which tools the Tutor called this turn
        session_completed:  True when bridge_to_practice was reached
    """
    messages = [
        {"role": "system", "content": system_prompt}
    ] + conversation_history + [
        {"role": "user", "content": learner_message}
    ]

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=messages,
        tools=TUTOR_TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=0.6
    )

    message = response.choices[0].message
    tools_called = []
    final_content = message.content or ""

    # Handle tool calls
    if message.tool_calls:
        tools_called = [tc.function.name for tc in message.tool_calls]
        logger.info(f"Tutor calling tools: {tools_called}")

        # Add assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        })

        # Execute tools and add results
        for tool_call in message.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            # Inject learner_id if not provided by model
            if "learner_id" not in args and learner_id:
                args["learner_id"] = learner_id
            if "section" not in args:
                args["section"] = section

            tool_result = execute_tutor_tool(tool_call.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

        # Get final response after tool results
        follow_up = client.chat.completions.create(
            model=QWEN_MODEL,
            messages=messages,
            tools=TUTOR_TOOL_SCHEMAS,
            tool_choice="none",  # No more tool calls in follow-up
            temperature=0.6
        )
        final_content = follow_up.choices[0].message.content or ""

    # Soft spine validation — LOG-ONLY. A regeneration retry doubles
    # turn latency (each Qwen call is 10-20s), which makes the tutor
    # feel frozen. Observability stays; enforcement is via the plan.
    try:
        check = validate_spine(final_content)
        if not check["passed"]:
            logger.info(
                f"spine_check_failed (log-only) "
                f"missing={check['triad']['missing'] if check['triad'] else []} "
                f"priorities={check['priority_count']}"
            )
    except Exception as e:
        logger.warning(f"Spine validation failed (non-blocking): {e}")

    clean_text, state = parse_state_tag(final_content)

    # Parse and record pedagogical action tags
    clean_text, actions = parse_action_tags(clean_text)
    if session_id:
        _record_actions(actions, session_id, learner_id, section)
        update_session_state(session_id, state)

    # Extract memories when tutor concludes drilling
    memories_extracted = 0
    session_completed = False
    if state == "bridge_to_practice" and learner_id:
        session_completed = True
        try:
            # Build conversation for memory extraction
            drill_history = conversation_history + [
                {"role": "user", "content": learner_message},
                {"role": "assistant", "content": final_content}
            ]
            memories = extract_chat_memories(
                learner_id=learner_id,
                section=section,
                conversation_history=drill_history
            )
            memories_extracted = len(memories)
            logger.info(
                f"Tutor extracted {memories_extracted} memories "
                f"for {learner_id} ({section})"
            )
        except Exception as e:
            logger.warning(f"Chat memory extraction failed: {e}")

        # Close out the pedagogy plan if the Tutor never tagged completion
        if session_id:
            try:
                plan = get_session_plan(session_id)
                if plan and not plan.get("outcome"):
                    complete_session_plan(session_id, "completed")
            except Exception as e:
                logger.warning(f"Plan completion failed: {e}")

    return {
        "message": clean_text,
        "state": state,
        "memories_extracted": memories_extracted,
        "tools_called": tools_called,
        "session_completed": session_completed,
        "session_id": session_id
    }


def _record_actions(
    actions: list,
    session_id: str,
    learner_id: str,
    section: str
) -> None:
    """
    Maps parsed [ACTION:] tags to pedagogical/hint event records.
    Best-effort — a failed record loses one data point, never the turn.
    """
    if not actions or not session_id:
        return

    plan = None
    try:
        plan = get_session_plan(session_id)
    except Exception:
        pass
    criterion_id = plan["target_criterion"] if plan else None
    framework_id = plan["dominant_framework"] if plan else None

    for entry in actions:
        try:
            action = entry["action"]
            params = entry.get("params", {})

            if action == "hint":
                record_hint(
                    session_id, learner_id, section,
                    hint_level=params["level"],
                    criterion_id=criterion_id,
                    framework_id=framework_id,
                )
                record_event(
                    session_id, learner_id, section, "hint_given",
                    criterion_id=criterion_id, framework_id=framework_id,
                    evidence={"level": params["level"]},
                )

            elif action == "attempt":
                result = params["result"]
                if result == "self_corrected":
                    record_event(
                        session_id, learner_id, section,
                        "self_correction_succeeded",
                        criterion_id=criterion_id, framework_id=framework_id,
                        success=True,
                    )
                    mark_last_hint_self_corrected(session_id, True)
                else:
                    success = result == "success"
                    record_event(
                        session_id, learner_id, section, "learner_attempted",
                        criterion_id=criterion_id, framework_id=framework_id,
                        success=success,
                    )
                    if not success:
                        mark_last_hint_self_corrected(session_id, False)

            elif action == "model_shown":
                record_event(
                    session_id, learner_id, section, "model_shown",
                    criterion_id=criterion_id, framework_id=framework_id,
                )

            elif action == "framework_started":
                record_event(
                    session_id, learner_id, section, "framework_started",
                    criterion_id=criterion_id, framework_id=framework_id,
                )

            elif action == "feedback_given":
                record_event(
                    session_id, learner_id, section, "feedback_given",
                    criterion_id=criterion_id, framework_id=framework_id,
                )

            elif action == "independent_check":
                record_event(
                    session_id, learner_id, section,
                    "independent_check_started",
                    criterion_id=criterion_id, framework_id=framework_id,
                )

            elif action == "complete":
                outcome = params.get("outcome", "completed")
                record_event(
                    session_id, learner_id, section, "framework_completed",
                    criterion_id=criterion_id, framework_id=framework_id,
                    evidence={"outcome": outcome},
                )
                complete_session_plan(session_id, outcome)

        except Exception as e:
            logger.warning(f"Failed to record action {entry}: {e}")


def _resolve_tool_calls(
    system_prompt: str,
    messages: list,
    tool_calls: list,
    learner_id: str
) -> str:
    """
    Executes tool calls and gets the Tutor's final response.
    Used when tool calls happen at session start.
    """
    for tool_call in tool_calls:
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            args = {}

        if "learner_id" not in args and learner_id:
            args["learner_id"] = learner_id

        tool_result = execute_tutor_tool(tool_call.function.name, args)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": tool_result
        })

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=messages,
        tools=TUTOR_TOOL_SCHEMAS,
        tool_choice="none",
        temperature=0.6
    )
    return response.choices[0].message.content or ""
