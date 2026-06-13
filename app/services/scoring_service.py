import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import call_qwen_for_json
from app.services.practice_service import get_rubric_summary
from app.utils.json_utils import safe_parse_json, extract_json_from_text

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_prompt_template(filename: str) -> str:
    """
    Loads a prompt template from the prompts/ folder.
    """
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def format_memories_for_prompt(memories: list) -> str:
    """
    Converts a list of memory dicts into a readable text block
    that Qwen can understand and reference.
    """
    if not memories:
        return "No previous memories exist for this learner. This may be their first attempt."

    lines = []
    weaknesses = [m for m in memories if m["memory_type"] == "weakness"]
    strengths = [m for m in memories if m["memory_type"] == "strength"]

    if weaknesses:
        lines.append("Previously observed WEAKNESSES:")
        for mem in weaknesses:
            confidence_pct = int(mem["confidence"] * 100)
            evidence = mem["evidence_count"]
            lines.append(
                f"  - [{mem['skill']}] {mem['memory_text']} "
                f"(confidence: {confidence_pct}%, seen across {evidence} attempt(s))"
            )

    if strengths:
        lines.append("\nPreviously observed STRENGTHS:")
        for mem in strengths:
            lines.append(f"  - [{mem['skill']}] {mem['memory_text']}")

    return "\n".join(lines)


def evaluate_writing(prompt: str, essay: str, memories: list = None) -> dict:
    """
    Evaluates a learner's essay against an IELTS writing prompt.

    Accepts an optional memories list. If memories are provided,
    they are formatted and injected into the prompt so Qwen gives
    personalised feedback based on the learner's history.
    """
    if memories is None:
        memories = []

    # Load the rubric summary for Writing
    rubric = get_rubric_summary("Writing")

    # Format memories into readable text for the prompt
    memory_context = format_memories_for_prompt(memories)

    # Load and fill the prompt template
    template = load_prompt_template("writing_evaluator_prompt.txt")
    full_prompt = template.format(
        memory_context=memory_context,
        prompt=prompt,
        essay=essay,
        rubric=rubric
    )

    # Call Qwen
    raw_response = call_qwen_for_json(full_prompt)

    # Parse the response safely
    # Parse the response safely
    try:
        result = safe_parse_json(raw_response)
    except ValueError:
        # If parsing fails, ask Qwen to fix its own JSON
        try:
            from app.services.qwen_service import fix_broken_json
            fixed_response = fix_broken_json(raw_response)
            result = safe_parse_json(fixed_response)
        except ValueError as e:
            raise Exception(f"Failed to parse scoring response: {e}")

    # Validate required fields
    required_fields = ["overall_feedback", "scores", "strengths",
                       "weaknesses", "recommended_next_step"]
    for field in required_fields:
        if field not in result:
            raise Exception(f"Qwen response missing required field: '{field}'")

    return result
