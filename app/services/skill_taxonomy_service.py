import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

RANK_NAMES = {
    1: "Beginner",
    2: "Developing",
    3: "Intermediate",
    4: "Proficient",
    5: "Advanced"
}


def load_taxonomy(section: str = "Writing") -> dict:
    """
    Loads the skill taxonomy for a given section.
    Currently only 'Writing' has a taxonomy file.
    """
    filename = f"skill_taxonomy_{section.lower()}.json"
    path = os.path.join(DATA_DIR, filename)

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No skill taxonomy found for section '{section}' "
            f"at {path}"
        )

    with open(path, "r") as f:
        return json.load(f)


def get_all_skill_ids(section: str = "Writing") -> list:
    """
    Returns a flat list of every skill_id in the taxonomy.
    Used when building the fixed-list prompt for Qwen in Phase C —
    Qwen must select from exactly these IDs, nothing else.
    """
    taxonomy = load_taxonomy(section)
    skill_ids = []
    for category in taxonomy["categories"]:
        for skill in category["skills"]:
            skill_ids.append(skill["skill_id"])
    return skill_ids


def get_skill_by_id(skill_id: str, section: str = "Writing") -> dict | None:
    """
    Returns the full skill definition (name, description, ranks)
    for a given skill_id.
    """
    taxonomy = load_taxonomy(section)
    for category in taxonomy["categories"]:
        for skill in category["skills"]:
            if skill["skill_id"] == skill_id:
                # Attach category info for convenience
                return {
                    **skill,
                    "category_id": category["category_id"],
                    "category_name": category["category_name"]
                }
    return None


def get_skills_flat(section: str = "Writing") -> list:
    """
    Returns every skill as a flat list (with category info attached),
    rather than nested under categories. Easier to iterate over
    when building prompts or tables.
    """
    taxonomy = load_taxonomy(section)
    flat = []
    for category in taxonomy["categories"]:
        for skill in category["skills"]:
            flat.append({
                **skill,
                "category_id": category["category_id"],
                "category_name": category["category_name"]
            })
    return flat


def get_rank_name(rank: int) -> str:
    """
    Converts a numeric rank (1-5) to its display name.
    """
    return RANK_NAMES.get(rank, "Unknown")


def format_skill_list_for_prompt(section: str = "Writing") -> str:
    """
    Builds a formatted text block listing every skill_id and its
    description. This is injected into the Qwen evaluator prompt
    in Phase C so Qwen can only choose from this fixed list —
    it cannot invent a new skill_id.
    """
    skills = get_skills_flat(section)
    lines = []
    current_category = None

    for skill in skills:
        if skill["category_name"] != current_category:
            current_category = skill["category_name"]
            lines.append(f"\n{current_category}:")
        lines.append(
            f"  - {skill['skill_id']}: {skill['skill_name']} — "
            f"{skill['description']}"
        )

    return "\n".join(lines)


def get_rank_definition(skill_id: str, rank: int, section: str = "Writing") -> str:
    """
    Returns the specific rank definition text for a skill at a
    given rank. Used when generating teaching content in Phase D —
    the lesson needs to explain what THIS rank and the NEXT rank
    look like.
    """
    skill = get_skill_by_id(skill_id, section)
    if not skill:
        return ""
    return skill["ranks"].get(str(rank), "")

# ─── BRIDGING TO THE FREE-TEXT MEMORY SYSTEM ──────────────────────────────────

# learner_memories.skill is free text Qwen chose itself (e.g. "Thesis
# Clarity", "Conclusion"). learner_skill_ranks.skill_id is a fixed taxonomy
# key (e.g. "tr_conclusion_synthesis"). This map lets us find the most
# likely matching free-text memories for a given fixed skill_id, so the
# Chat Coach can quote a learner's ACTUAL essay observation rather than
# just stating a rank number.
SKILL_ID_TO_MEMORY_LABELS = {
    "tr_full_coverage": ["Task Response", "Idea Development"],
    "tr_position_clarity": ["Thesis Clarity"],
    "tr_idea_development": ["Idea Development"],
    "tr_conclusion_synthesis": ["Conclusion", "Thesis Clarity"],
    "cc_logical_progression": ["Organization"],
    "cc_paragraphing": ["Organization"],
    "cc_cohesive_devices": ["Organization", "Grammar"],
    "lr_range": ["Vocabulary"],
    "lr_precision": ["Vocabulary"],
    "lr_spelling_word_formation": ["Vocabulary", "Grammar"],
    "gra_sentence_variety": ["Grammar"],
    "gra_accuracy": ["Grammar"],
    "gra_punctuation": ["Grammar"]
}


def get_memory_labels_for_skill(skill_id: str) -> list:
    """
    Returns the free-text memory 'skill' labels most likely to
    correspond to a given fixed skill_id. Used to search
    learner_memories for relevant evidence to quote.
    """
    return SKILL_ID_TO_MEMORY_LABELS.get(skill_id, [])
