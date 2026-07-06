import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import client, QWEN_TURBO_MODEL
from app.services.skill_taxonomy_service import (
    get_all_skill_ids,
    format_skill_list_for_prompt
)
from app.utils.json_utils import safe_parse_json, extract_json_from_text

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

VALID_CLASSIFICATIONS = {
    "demonstrated_strength",
    "demonstrated_weakness",
    "not_applicable"
}


def load_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def classify_writing_skills(prompt: str, essay: str, section: str = "Writing") -> dict:
    """
    Classifies a learner's essay against every skill in the fixed
    taxonomy. Returns a dict mapping skill_id -> classification.

    This is a SEPARATE Qwen call from the main scoring call (by
    design — keeps each response shorter and easier to parse
    reliably, and lets one call fail without breaking the other).

    Any skill_id missing from Qwen's response, or with an invalid
    classification value, is defaulted to "not_applicable" rather
    than raising an error — we never want a malformed response to
    block the learner from seeing their essay feedback.
    """
    expected_skill_ids = set(get_all_skill_ids(section))
    skill_list_text = format_skill_list_for_prompt(section)

    template = load_prompt_template("skill_classifier_prompt.txt")
    full_prompt = template.format(
        prompt=prompt,
        essay=essay,
        skill_list=skill_list_text
    )

    try:
        response = client.chat.completions.create(
            model=QWEN_TURBO_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.1
        )
        raw_response = response.choices[0].message.content
    except Exception as e:
        # If the call fails entirely, mark everything not_applicable
        # rather than blocking the learner's feedback flow
        print(f"Skill classification call failed: {e}")
        return {skill_id: "not_applicable" for skill_id in expected_skill_ids}

    try:
        classifications = safe_parse_json(raw_response)
    except ValueError:
        try:
            classifications = extract_json_from_text(raw_response)
        except ValueError as e:
            print(f"Could not parse skill classification response: {e}")
            return {skill_id: "not_applicable" for skill_id in expected_skill_ids}

    if not isinstance(classifications, dict):
        print("Skill classification response was not a dict")
        return {skill_id: "not_applicable" for skill_id in expected_skill_ids}

    # Validate strictly against the fixed list -- this is the
    # safety net that prevents Qwen from inventing skill_ids or
    # using invalid classification values
    validated = {}
    for skill_id in expected_skill_ids:
        value = classifications.get(skill_id, "not_applicable")
        if value not in VALID_CLASSIFICATIONS:
            print(
                f"Invalid classification '{value}' for "
                f"'{skill_id}' -- defaulting to not_applicable"
            )
            value = "not_applicable"
        validated[skill_id] = value

    # Log any extra/invented keys Qwen returned but ignore them --
    # we only act on the fixed list, nothing else
    extra_keys = set(classifications.keys()) - expected_skill_ids
    if extra_keys:
        print(f"Ignoring invented skill_ids from Qwen: {extra_keys}")

    return validated
