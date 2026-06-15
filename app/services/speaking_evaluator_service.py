import os
import sys
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import call_qwen
from app.services.tts_service import examiner_speak
from app.utils.json_utils import safe_parse_json, extract_json_from_text

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def format_memories_for_prompt(memories: list) -> str:
    """
    Formats retrieved speaking memories for injection
    into the evaluator prompt.
    """
    if not memories:
        return "No previous speaking memories. This may be the learner's first speaking attempt."

    lines = []
    weaknesses = [m for m in memories if m["memory_type"] == "weakness"]
    strengths = [m for m in memories if m["memory_type"] == "strength"]

    if weaknesses:
        lines.append("Previously observed weaknesses:")
        for mem in weaknesses:
            confidence_pct = int(mem["confidence"] * 100)
            lines.append(
                f"  - [{mem['skill']}] {mem['memory_text']} "
                f"(confidence: {confidence_pct}%)"
            )

    if strengths:
        lines.append("Previously observed strengths:")
        for mem in strengths:
            lines.append(f"  - [{mem['skill']}] {mem['memory_text']}")

    return "\n".join(lines)


def format_part1_responses(questions: list, responses: dict) -> str:
    """
    Formats Part 1 questions and responses for the prompt.
    responses is a dict mapping question index to transcription text.
    """
    lines = []
    for i, question in enumerate(questions):
        response = responses.get(str(i), "").strip()
        lines.append(f"Q: {question}")
        lines.append(f"A: {response if response else '[No response recorded]'}")
        lines.append("")
    return "\n".join(lines)


def format_part3_responses(questions: list, responses: dict) -> str:
    """
    Formats Part 3 questions and responses for the prompt.
    Same structure as Part 1 formatting.
    """
    return format_part1_responses(questions, responses)


def parse_evaluator_response(raw_response: str) -> dict:
    """
    Parses the evaluator response which contains two sections:
    1. The spoken feedback text (before ---SCORES---)
    2. A JSON scores block (between ---SCORES--- and ---END---)

    Returns a dict with:
    - feedback_text: the examiner's spoken feedback
    - scores: the parsed JSON scores dict
    """
    # Split on the scores delimiter
    parts = raw_response.split("---SCORES---")

    if len(parts) < 2:
        # No scores section found — return raw text with empty scores
        return {
            "feedback_text": raw_response.strip(),
            "scores": {}
        }

    feedback_text = parts[0].strip()

    # Extract the JSON from between ---SCORES--- and ---END---
    scores_section = parts[1]
    scores_section = scores_section.split("---END---")[0].strip()

    try:
        scores = safe_parse_json(scores_section)
    except ValueError:
        try:
            scores = extract_json_from_text(scores_section)
        except ValueError:
            scores = {}

    return {
        "feedback_text": feedback_text,
        "scores": scores
    }


def evaluate_speaking_attempt(
    prompt_set: dict,
    part1_responses: dict,
    part2_response: str,
    part3_responses: dict,
    memories: list = None
) -> dict:
    """
    Evaluates a complete three part speaking attempt.

    Arguments:
    - prompt_set: the full prompt set dict from speaking_prompts.json
    - part1_responses: dict mapping question index to transcription
    - part2_response: transcription of the Part 2 monologue
    - part3_responses: dict mapping question index to transcription
    - memories: list of existing speaking memories for this learner

    Returns a dict with:
    - feedback_text: examiner's written feedback
    - audio_bytes: Cherry's spoken version of the feedback
    - scores: structured scores dict
    - success: bool
    - error: error message if failed
    """
    if memories is None:
        memories = []

    try:
        # Format all responses for the prompt
        part1_text = format_part1_responses(
            prompt_set["part1"]["questions"],
            part1_responses
        )

        part3_text = format_part3_responses(
            prompt_set["part3"]["questions"],
            part3_responses
        )

        memory_context = format_memories_for_prompt(memories)

        # Load and fill the evaluator prompt
        template = load_prompt_template("speaking_evaluator_prompt.txt")
        full_prompt = template.format(
            topic=prompt_set["topic"],
            part1_responses=part1_text,
            part2_title=prompt_set["part2"]["title"],
            part2_response=part2_response if part2_response else "[No response recorded]",
            part3_responses=part3_text,
            memory_context=memory_context
        )

        # Call Qwen with slightly higher temperature for natural tone
        # 0.5 gives more natural conversational feedback
        raw_response = call_qwen(
            prompt=full_prompt,
            temperature=0.5
        )

        # Parse the response into feedback text and scores
        parsed = parse_evaluator_response(raw_response)
        feedback_text = parsed["feedback_text"]
        scores = parsed["scores"]

        # Generate spoken audio of the feedback using TTS
        tts_result = examiner_speak(feedback_text)

        return {
            "success": True,
            "feedback_text": feedback_text,
            "audio_bytes": tts_result.get("audio_bytes"),
            "tts_success": tts_result.get("success", False),
            "scores": scores,
            "part1_responses": part1_responses,
            "part2_response": part2_response,
            "part3_responses": part3_responses,
            "topic": prompt_set["topic"],
            "difficulty": prompt_set["difficulty"],
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "feedback_text": "",
            "audio_bytes": None,
            "tts_success": False,
            "scores": {},
            "error": str(e)
        }
