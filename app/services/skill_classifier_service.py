"""
app/services/skill_classifier_service.py

Classifies practice attempts against the fixed skill taxonomy
for all four IELTS sections.

Each section has its own prompt template and skill list.
All classification calls use qwen-turbo (fast, cheap, sufficient
for constrained 3-way output).

The rank engine (apply_skill_classifications_batch) is called
after classification — it is deterministic and never uses AI.
"""

import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import client, QWEN_TURBO_MODEL
from app.services.skill_taxonomy_service import (
    get_all_skill_ids,
    format_skill_list_for_prompt
)
from app.utils.json_utils import safe_parse_json, extract_json_from_text
from app.utils.logger import get_logger

logger = get_logger("services.skill_classifier")

PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "prompts"
)

VALID_CLASSIFICATIONS = {
    "demonstrated_strength",
    "demonstrated_weakness",
    "not_applicable"
}

SECTION_PROMPTS = {
    "Writing":   "skill_classifier_prompt.txt",
    "Reading":   "reading_skill_classifier_prompt.txt",
    "Speaking":  "speaking_skill_classifier_prompt.txt",
    "Listening": "listening_skill_classifier_prompt.txt",
}


def load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def _call_classifier(prompt: str, section: str) -> str:
    """Makes the qwen-turbo classification call."""
    response = client.chat.completions.create(
        model=QWEN_TURBO_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content


def _validate_classifications(
    raw: dict,
    expected_skill_ids: set,
    section: str
) -> dict:
    """
    Validates classifications against the fixed skill list.
    Defaults to not_applicable for missing or invalid values.
    Logs any invented skill_ids from the model.
    """
    validated = {}
    for skill_id in expected_skill_ids:
        value = raw.get(skill_id, "not_applicable")
        if value not in VALID_CLASSIFICATIONS:
            logger.warning(
                f"[{section}] Invalid classification '{value}' "
                f"for '{skill_id}' — defaulting to not_applicable"
            )
            value = "not_applicable"
        validated[skill_id] = value

    extra_keys = set(raw.keys()) - expected_skill_ids
    if extra_keys:
        logger.warning(
            f"[{section}] Ignoring invented skill_ids: {extra_keys}"
        )

    return validated


def _parse_and_validate(
    raw_response: str,
    expected_skill_ids: set,
    section: str
) -> dict:
    """Parses the raw response and validates against the skill list."""
    try:
        parsed = safe_parse_json(raw_response)
    except ValueError:
        try:
            parsed = extract_json_from_text(raw_response)
        except ValueError as e:
            logger.error(
                f"[{section}] Could not parse classifier response: {e}"
            )
            return {sid: "not_applicable" for sid in expected_skill_ids}

    if not isinstance(parsed, dict):
        logger.error(f"[{section}] Classifier response was not a dict")
        return {sid: "not_applicable" for sid in expected_skill_ids}

    return _validate_classifications(parsed, expected_skill_ids, section)


def classify_writing_skills(
    prompt: str,
    essay: str,
    section: str = "Writing"
) -> dict:
    """
    Classifies a Writing essay against all 13 Writing sub-skills.
    Called as a BackgroundTask after essay evaluation.
    """
    expected_ids = set(get_all_skill_ids(section))
    skill_list_text = format_skill_list_for_prompt(section)

    template = load_prompt(SECTION_PROMPTS[section])
    full_prompt = template.format(
        prompt=prompt,
        essay=essay,
        skill_list=skill_list_text
    )

    try:
        raw = _call_classifier(full_prompt, section)
    except Exception as e:
        logger.error(f"[Writing] Classifier call failed: {e}")
        return {sid: "not_applicable" for sid in expected_ids}

    return _parse_and_validate(raw, expected_ids, section)


def classify_reading_skills(
    passage_title: str,
    question_results: list,
    skill_accuracy: dict,
    total_score: int,
    max_score: int,
    percentage: float
) -> dict:
    """
    Classifies a Reading attempt against all 10 Reading sub-skills.
    Uses question results and skill accuracy data rather than
    raw text — Reading is assessed by performance, not by prose.
    """
    section = "Reading"
    expected_ids = set(get_all_skill_ids(section))
    skill_list_text = format_skill_list_for_prompt(section)

    # Format question results for the prompt
    results_text = "\n".join([
        f"Q{i+1}: {r['question']} "
        f"[{'✓' if r['is_correct'] else '✗'}] "
        f"({r.get('score', 0)}/{r.get('max_score', 1)}) "
        f"Type: {r.get('question_type', 'unknown')}"
        for i, r in enumerate(question_results)
    ])

    accuracy_text = "\n".join([
        f"{skill}: {acc}%"
        for skill, acc in skill_accuracy.items()
    ])

    template = load_prompt(SECTION_PROMPTS[section])
    full_prompt = template.format(
        passage_title=passage_title,
        question_results=results_text,
        skill_accuracy=accuracy_text,
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        skill_list=skill_list_text
    )

    try:
        raw = _call_classifier(full_prompt, section)
    except Exception as e:
        logger.error(f"[Reading] Classifier call failed: {e}")
        return {sid: "not_applicable" for sid in expected_ids}

    return _parse_and_validate(raw, expected_ids, section)


def classify_speaking_skills(
    topic: str,
    part1_responses: dict,
    part2_response: str,
    part3_responses: dict,
    feedback_text: str,
    scores: dict
) -> dict:
    """
    Classifies a Speaking attempt against all 9 Speaking sub-skills.
    Uses transcribed responses + examiner feedback + band scores.
    """
    section = "Speaking"
    expected_ids = set(get_all_skill_ids(section))
    skill_list_text = format_skill_list_for_prompt(section)

    # Format responses for prompt
    p1_text = "\n".join([
        f"Q{int(i)+1}: {text}"
        for i, text in part1_responses.items()
    ]) or "No Part 1 responses recorded"

    p3_text = "\n".join([
        f"Q{int(i)+1}: {text}"
        for i, text in part3_responses.items()
    ]) or "No Part 3 responses recorded"

    band_text = "\n".join([
        f"{k}: {v}" for k, v in scores.items()
        if k in ['fluency_coherence', 'lexical_resource',
                 'grammatical_range', 'pronunciation_clarity',
                 'overall_band']
    ])

    template = load_prompt(SECTION_PROMPTS[section])
    full_prompt = template.format(
        topic=topic,
        part1_responses=p1_text,
        part2_response=part2_response or "No Part 2 response recorded",
        part3_responses=p3_text,
        feedback_text=feedback_text or "No feedback available",
        band_scores=band_text,
        skill_list=skill_list_text
    )

    try:
        raw = _call_classifier(full_prompt, section)
    except Exception as e:
        logger.error(f"[Speaking] Classifier call failed: {e}")
        return {sid: "not_applicable" for sid in expected_ids}

    return _parse_and_validate(raw, expected_ids, section)


def classify_listening_skills(
    track_title: str,
    part: int,
    question_results: list,
    skill_accuracy: dict,
    total_score: int,
    max_score: int,
    percentage: float
) -> dict:
    """
    Classifies a Listening attempt against all 8 Listening sub-skills.
    Similar to Reading — uses performance data rather than raw audio.
    """
    section = "Listening"
    expected_ids = set(get_all_skill_ids(section))
    skill_list_text = format_skill_list_for_prompt(section)

    part_descriptions = {
        1: "Social conversation (form/note completion)",
        2: "Monologue/announcement (multiple choice, matching)",
        3: "Academic discussion (multiple choice, matching)",
        4: "Lecture/talk (note/sentence completion)"
    }

    results_text = "\n".join([
        f"Q{i+1}: {r['question']} "
        f"[{'✓' if r['is_correct'] else '✗'}] "
        f"Type: {r.get('question_type', 'unknown')} "
        f"Answer: {r.get('learner_answer', '')} "
        f"Correct: {r.get('correct_answer', '')}"
        for i, r in enumerate(question_results)
    ])

    accuracy_text = "\n".join([
        f"{skill}: {acc}%"
        for skill, acc in skill_accuracy.items()
    ])

    template = load_prompt(SECTION_PROMPTS[section])
    full_prompt = template.format(
        track_title=track_title,
        part=part,
        part_description=part_descriptions.get(part, "Listening exercise"),
        question_results=results_text,
        skill_accuracy=accuracy_text,
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        skill_list=skill_list_text
    )

    try:
        raw = _call_classifier(full_prompt, section)
    except Exception as e:
        logger.error(f"[Listening] Classifier call failed: {e}")
        return {sid: "not_applicable" for sid in expected_ids}

    return _parse_and_validate(raw, expected_ids, section)
