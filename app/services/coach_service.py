"""
app/services/coach_service.py

The Coach agent — evaluates every practice submission, gathers
evidence via tools, makes informed classification decisions, and
writes memories grounded in real learner work.

Replaces the four separate background task chains
(_writing_post_tasks, _reading_post_tasks, etc.) with a single
Coach agent that runs the same pipeline but with tool access,
making its decisions explicit and auditable.

Architecture:
  COACH AGENT (this file)
    ↓ calls tools to gather evidence
    get_skill_rank        — reads current rank + streak
    get_learner_memories  — reads existing patterns
    get_recent_attempt    — reads actual learner work
    ↓ makes AI judgement
    submit_classification — triggers deterministic rank engine
    write_memory          — saves new coaching observation
    update_memory         — updates existing memory confidence

  DETERMINISTIC RANK ENGINE (memory_service.py, unchanged)
    apply_skill_classifications_batch()
    clean_streak += 1 on strength
    clean_streak = 0 on weakness
    rank up when streak >= 3
    full audit trail in learner_skill_ranks table

The AI judges the evidence. The engine enforces the rules.
Neither can act without the other.
"""

import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import client, QWEN_TURBO_MODEL, QWEN_MODEL
from app.services.agent_tools import (
    COACH_TOOL_SCHEMAS,
    execute_coach_tool
)
from app.services.skill_taxonomy_service import (
    get_all_skill_ids,
    format_skill_list_for_prompt
)
from app.utils.logger import get_logger

logger = get_logger("services.coach")

# ─── Coach system prompt ──────────────────────────────────────────────────────

COACH_SYSTEM_PROMPT = """You are the IELTS MemoryCoach — an expert AI coach
that evaluates learner practice submissions and maintains their coaching profile.

Your job after every submission:
1. Call get_learner_memories to understand existing patterns
2. Call get_recent_attempt to see their actual work
3. For each skill in the taxonomy, call get_skill_rank to see current state
4. Call submit_classification with your assessment of EVERY skill
5. Call write_memory for each new coaching observation (1-3 memories max)
6. Call update_memory for existing memories that new evidence confirms or contradicts

Classification rules:
- demonstrated_strength: clear evidence the learner controls this skill
- demonstrated_weakness: clear evidence of a problem with this skill
- not_applicable: this attempt doesn't provide enough evidence to judge

Memory writing rules:
- Be specific — reference what the learner actually did
- One memory per distinct skill observation
- confidence 0.6-0.7 for new observations
- Never write vague memories like "learner needs improvement"

You MUST call submit_classification before finishing.
You MUST classify every skill in the taxonomy — no omissions.
After all tool calls are complete, write a brief summary (2-3 sentences)
of what you observed and what the learner should focus on next.
"""


# ─── Agent loop ───────────────────────────────────────────────────────────────

def run_coach_agent(
    learner_id: str,
    section: str,
    submission_context: dict,
    max_iterations: int = 10
) -> dict:
    """
    Runs the Coach agent loop for a practice submission.

    The agent calls tools to gather evidence, then makes
    classification and memory decisions. Loops until Qwen
    stops returning tool calls or max_iterations is reached.

    Args:
        learner_id:         Learner's unique ID
        section:            IELTS section (Writing/Reading/Speaking/Listening)
        submission_context: What was submitted — varies by section:
            Writing:  {prompt, essay, scores, feedback}
            Reading:  {passage_title, question_results, skill_accuracy, score}
            Speaking: {topic, scores, feedback_text}
            Listening:{track_title, part, question_results, skill_accuracy, score}
        max_iterations:     Safety cap on tool call loops

    Returns:
        {
            "success": bool,
            "summary": str,           — Coach's summary observation
            "tools_called": list,     — which tools were called
            "rank_ups": list,         — any rank-up events
            "memories_written": int,  — new memories saved
            "error": str | None
        }
    """
    skill_list = format_skill_list_for_prompt(section)

    # Build the submission brief for the Coach
    submission_brief = _format_submission_brief(
        section, submission_context, skill_list
    )

    messages = [
        {"role": "system", "content": COACH_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Learner ID: {learner_id}\n"
            f"Section: {section}\n\n"
            f"{submission_brief}\n\n"
            f"Skill taxonomy to classify:\n{skill_list}\n\n"
            f"Begin your evaluation. Use your tools to gather evidence, "
            f"then classify all skills and write coaching memories."
        )}
    ]

    tools_called = []
    rank_ups = []
    memories_written = 0
    summary = ""
    iterations = 0

    logger.info(f"Coach agent starting for {learner_id} ({section})")

    while iterations < max_iterations:
        iterations += 1

        try:
            response = client.chat.completions.create(
                model=QWEN_MODEL,
                messages=messages,
                tools=COACH_TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.2  # Low temp for consistent classification
            )
        except Exception as e:
            logger.error(f"Coach agent Qwen call failed: {e}")
            return {
                "success": False,
                "summary": "",
                "tools_called": tools_called,
                "rank_ups": rank_ups,
                "memories_written": memories_written,
                "error": str(e)
            }

        choice = response.choices[0]
        message = choice.message

        # Add assistant message to history
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
                for tc in (message.tool_calls or [])
            ] if message.tool_calls else []
        })

        # No more tool calls — agent is done
        if not message.tool_calls:
            summary = message.content or ""
            logger.info(
                f"Coach agent complete: "
                f"{len(tools_called)} tools called, "
                f"{memories_written} memories written, "
                f"{len(rank_ups)} rank-ups"
            )
            break

        # Execute each tool call
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            logger.info(f"Coach calling tool: {tool_name}")
            tools_called.append(tool_name)

            # Execute the tool
            tool_result = execute_coach_tool(tool_name, args)

            # Track outcomes
            if tool_name == "submit_classification":
                result_data = json.loads(tool_result)
                rank_ups.extend(result_data.get("ranked_up", []))

            elif tool_name == "write_memory":
                result_data = json.loads(tool_result)
                if result_data.get("saved"):
                    memories_written += 1

            # Add tool result to message history
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

    if iterations >= max_iterations:
        logger.warning(f"Coach agent hit max iterations ({max_iterations})")

    return {
        "success": True,
        "summary": summary,
        "tools_called": tools_called,
        "rank_ups": rank_ups,
        "memories_written": memories_written,
        "error": None
    }


# ─── Submission brief formatters ──────────────────────────────────────────────

def _format_submission_brief(
    section: str,
    context: dict,
    skill_list: str
) -> str:
    """
    Formats the submission context into a readable brief
    for the Coach agent's initial message.
    """
    if section == "Writing":
        scores_text = "\n".join([
            f"  {k.replace('_', ' ').title()}: {v}/5"
            for k, v in context.get("scores", {}).items()
        ])
        return (
            f"## Writing Submission\n\n"
            f"**Prompt:** {context.get('prompt', '')}\n\n"
            f"**Essay excerpt:**\n{context.get('essay', '')[:800]}...\n\n"
            f"**Scores:**\n{scores_text}\n\n"
            f"**Evaluator feedback:**\n{context.get('feedback', '')[:600]}"
        )

    elif section == "Reading":
        q_lines = "\n".join([
            f"  Q{i+1} [{r.get('question_type', '')}] "
            f"[{r.get('skill', '')}] "
            f"{'✓' if r.get('is_correct') else '✗'} "
            f"({r.get('score', 0)}/{r.get('max_score', 1)})"
            for i, r in enumerate(context.get("question_results", []))
        ])
        acc_lines = "\n".join([
            f"  {skill}: {acc}%"
            for skill, acc in context.get("skill_accuracy", {}).items()
        ])
        return (
            f"## Reading Submission\n\n"
            f"**Passage:** {context.get('passage_title', '')}\n\n"
            f"**Score:** {context.get('total_score', 0)} / "
            f"{context.get('max_score', 0)} "
            f"({context.get('percentage', 0)}%)\n\n"
            f"**Question results:**\n{q_lines}\n\n"
            f"**Skill accuracy:**\n{acc_lines}"
        )

    elif section == "Speaking":
        scores = context.get("scores", {})
        scores_text = "\n".join([
            f"  {k.replace('_', ' ').title()}: {v}/9"
            for k, v in scores.items()
            if k in ['fluency_coherence', 'lexical_resource',
                     'grammatical_range', 'pronunciation_clarity']
        ])
        return (
            f"## Speaking Submission\n\n"
            f"**Topic:** {context.get('topic', '')}\n\n"
            f"**Overall Band:** {scores.get('overall_band', '?')}/9\n\n"
            f"**Criterion scores:**\n{scores_text}\n\n"
            f"**Feedback:**\n{context.get('feedback_text', '')[:600]}"
        )

    elif section == "Listening":
        q_lines = "\n".join([
            f"  Q{i+1} [{r.get('question_type', '')}] "
            f"[{r.get('skill', '')}] "
            f"{'✓' if r.get('is_correct') else '✗'}"
            for i, r in enumerate(context.get("question_results", []))
        ])
        acc_lines = "\n".join([
            f"  {skill}: {acc}%"
            for skill, acc in context.get("skill_accuracy", {}).items()
        ])
        return (
            f"## Listening Submission\n\n"
            f"**Track:** {context.get('track_title', '')} "
            f"(Part {context.get('part', '?')})\n\n"
            f"**Score:** {context.get('total_score', 0)} / "
            f"{context.get('max_score', 0)} "
            f"({context.get('percentage', 0)}%)\n\n"
            f"**Question results:**\n{q_lines}\n\n"
            f"**Skill accuracy:**\n{acc_lines}"
        )

    return f"## {section} Submission\n\n{json.dumps(context, indent=2)}"


# ─── Section-specific entry points ────────────────────────────────────────────
# These replace the background task chains in the route files.
# Each assembles the submission context and calls run_coach_agent.

def coach_writing_submission(
    learner_id: str,
    prompt: str,
    essay: str,
    score_result: dict,
    feedback: str
) -> dict:
    """Coach evaluation after a Writing submission."""
    context = {
        "prompt": prompt,
        "essay": essay,
        "scores": score_result.get("scores", {}),
        "feedback": feedback
    }
    return run_coach_agent(learner_id, "Writing", context)


def coach_reading_submission(
    learner_id: str,
    attempt_result: dict
) -> dict:
    """Coach evaluation after a Reading submission."""
    return run_coach_agent(learner_id, "Reading", attempt_result)


def coach_speaking_submission(
    learner_id: str,
    attempt_result: dict
) -> dict:
    """Coach evaluation after a Speaking submission."""
    return run_coach_agent(learner_id, "Speaking", attempt_result)


def coach_listening_submission(
    learner_id: str,
    attempt_result: dict
) -> dict:
    """Coach evaluation after a Listening submission."""
    return run_coach_agent(learner_id, "Listening", attempt_result)
