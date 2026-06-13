import json
import random
import os

# Build the path to the data folder regardless of where the script is run from
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_writing_prompts() -> list:
    """
    Loads all writing prompts from the JSON file.
    Returns a list of prompt dictionaries.
    """
    path = os.path.join(DATA_DIR, "writing_prompts.json")
    with open(path, "r") as f:
        return json.load(f)


def get_random_writing_prompt() -> dict:
    """
    Returns a single random writing prompt.
    This is what the Writing Coach page calls to get today's prompt.
    """
    prompts = load_writing_prompts()
    return random.choice(prompts)


def get_writing_prompt_by_id(prompt_id: str) -> dict | None:
    """
    Returns a specific prompt by its ID.
    Useful when we want to reload the same prompt after a page refresh.
    """
    prompts = load_writing_prompts()
    for prompt in prompts:
        if prompt["prompt_id"] == prompt_id:
            return prompt
    return None


def get_prompts_by_difficulty(difficulty: str) -> list:
    """
    Returns all prompts matching a difficulty level.
    difficulty options: 'beginner', 'intermediate', 'advanced'
    """
    prompts = load_writing_prompts()
    return [p for p in prompts if p.get("difficulty") == difficulty]


def load_rubric(section: str) -> dict:
    """
    Loads the scoring rubric for a given section.
    e.g. load_rubric('Writing') returns the Writing rubric dict.
    """
    path = os.path.join(DATA_DIR, "rubrics.json")
    with open(path, "r") as f:
        rubrics = json.load(f)
    return rubrics.get(section, {})


def get_rubric_summary(section: str) -> str:
    """
    Returns a plain text summary of the rubric for use in Qwen prompts.
    This is what we'll pass to the AI so it knows how to score.
    """
    rubric = load_rubric(section)
    if not rubric:
        return ""

    lines = []
    skills = rubric.get("skills", {})
    max_score = rubric.get("max_score_per_skill", 5)

    for skill_key, skill_data in skills.items():
        lines.append(f"- {skill_data['name']} (max {max_score} points): {skill_data['description']}")

    return "\n".join(lines)