import os
import sys
import json
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_speaking_prompts() -> list:
    """
    Loads all speaking prompt sets from the JSON file.
    """
    path = os.path.join(DATA_DIR, "speaking_prompts.json")
    with open(path, "r") as f:
        return json.load(f)


def get_random_prompt_set(difficulty: str = None) -> dict:
    """
    Returns a random speaking prompt set.
    Optionally filtered by difficulty level.
    """
    prompts = load_speaking_prompts()

    if difficulty:
        prompts = [p for p in prompts if p["difficulty"] == difficulty]

    if not prompts:
        raise ValueError(f"No prompt sets found for difficulty: {difficulty}")

    return random.choice(prompts)


def get_prompt_set_by_id(prompt_set_id: str) -> dict | None:
    """
    Returns a specific prompt set by ID.
    Used to reload the same set without changing it on refresh.
    """
    prompts = load_speaking_prompts()
    for p in prompts:
        if p["prompt_set_id"] == prompt_set_id:
            return p
    return None


def get_all_prompt_sets_summary() -> list:
    """
    Returns a lightweight summary of all prompt sets.
    Used on the selection screen.
    """
    prompts = load_speaking_prompts()
    return [
        {
            "prompt_set_id": p["prompt_set_id"],
            "topic": p["topic"],
            "difficulty": p["difficulty"],
            "part1_title": p["part1"]["title"],
            "part2_title": p["part2"]["title"],
            "part3_title": p["part3"]["title"]
        }
        for p in prompts
    ]


def get_prompts_by_difficulty(difficulty: str) -> list:
    """
    Returns all prompt sets for a given difficulty.
    """
    prompts = load_speaking_prompts()
    return [p for p in prompts if p["difficulty"] == difficulty]


def format_part2_cue_card(prompt_set: dict) -> str:
    """
    Returns the Part 2 cue card text formatted for display.
    """
    return prompt_set["part2"]["cue_card"]


def get_session_structure(prompt_set: dict) -> dict:
    """
    Returns the full session structure for a prompt set.
    This is what the Speaking Coach page uses to render
    all three parts in order.

    Returns:
    - part1: list of questions
    - part2: cue card text + timing
    - part3: list of questions
    - topic and difficulty metadata
    """
    return {
        "prompt_set_id": prompt_set["prompt_set_id"],
        "topic": prompt_set["topic"],
        "difficulty": prompt_set["difficulty"],
        "part1": {
            "title": prompt_set["part1"]["title"],
            "questions": prompt_set["part1"]["questions"]
        },
        "part2": {
            "title": prompt_set["part2"]["title"],
            "cue_card": prompt_set["part2"]["cue_card"],
            "preparation_time": prompt_set["part2"]["preparation_time"],
            "speaking_time": prompt_set["part2"]["speaking_time"]
        },
        "part3": {
            "title": prompt_set["part3"]["title"],
            "questions": prompt_set["part3"]["questions"]
        }
    }
