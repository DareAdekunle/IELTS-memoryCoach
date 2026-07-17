import os
import sys
import json
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_speaking_prompts() -> list:
    path = os.path.join(DATA_DIR, "speaking_prompts.json")
    with open(path, "r") as f:
        return json.load(f)


def get_random_prompt_set(difficulty: str = None) -> dict:
    """Returns a random speaking prompt set, optionally filtered by difficulty."""
    prompts = load_speaking_prompts()
    if difficulty:
        prompts = [p for p in prompts if p["difficulty"] == difficulty]
    if not prompts:
        raise ValueError(f"No prompt sets found for difficulty: {difficulty}")
    return random.choice(prompts)


def get_adaptive_prompt_set(learner_id: str) -> dict:
    """
    Returns an unseen speaking prompt set matched to the learner's band level.
    Cycles back through seen prompts only when all at the level are exhausted.
    """
    from app.services.practice_service import get_adaptive_difficulty, _get_unseen_or_cycle
    difficulty = get_adaptive_difficulty(learner_id, "Speaking")
    prompts = load_speaking_prompts()
    filtered = [p for p in prompts if p["difficulty"] == difficulty]
    if not filtered:
        filtered = prompts
    return _get_unseen_or_cycle(filtered, learner_id, "Speaking", "prompt_set_id")


def get_prompt_set_by_id(prompt_set_id: str) -> dict | None:
    prompts = load_speaking_prompts()
    for p in prompts:
        if p["prompt_set_id"] == prompt_set_id:
            return p
    return None


def get_all_prompt_sets_summary() -> list:
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
    prompts = load_speaking_prompts()
    return [p for p in prompts if p["difficulty"] == difficulty]


def format_part2_cue_card(prompt_set: dict) -> str:
    return prompt_set["part2"]["cue_card"]


def get_session_structure(prompt_set: dict) -> dict:
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
