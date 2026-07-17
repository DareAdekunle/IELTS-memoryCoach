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

# ─── Band mapping ─────────────────────────────────────────────────────────────
# Maps rank (1-5) to the BASE IELTS band for that level.
# The 0.5 increment comes from clean_streak within the rank:
#   streak 0   → base band          (e.g. rank 2, streak 0 = Band 5.0)
#   streak 1+  → base band + 0.5   (e.g. rank 2, streak 1 = Band 5.5)
# Bands can fall back within a rank when weakness resets streak to 0.
# No band is shown until the learner has at least one attempt (evidence > 0).
#
# Band philosophy:
#   Rank 1 → Band 4.0  — emerging, first evidence of skill awareness
#   Rank 2 → Band 5.0  — developing, inconsistent but present
#   Rank 3 → Band 6.0  — competent, reliable under normal conditions
#   Rank 4 → Band 7.0  — proficient, consistent and accurate
#   Rank 5 → Band 8.0  — advanced, flexible and precise

RANK_TO_BASE_BAND = {
    1: 4.0,
    2: 5.0,
    3: 6.0,
    4: 7.0,
    5: 8.0,
}


def get_band_estimate(
    current_rank: int,
    clean_streak: int,
    total_evidence: int
) -> float | None:
    """
    Returns an estimated IELTS band (0.5 precision) for a skill
    based on its current rank and clean streak.

    Returns None if the learner has no evidence yet — no band
    is shown until at least one practice attempt exists.

    Band movement:
      streak 0   → base band for this rank
      streak 1+  → base band + 0.5 (building toward next rank)

    This means:
      - A weakness (streak reset to 0) drops the band back to base
      - Consistent strength (streak 1+) lifts the band by 0.5
      - Ranking up lifts the base band by a full point
    """
    if total_evidence == 0:
        return None

    base = RANK_TO_BASE_BAND.get(current_rank, 4.0)
    bonus = 0.5 if clean_streak >= 1 else 0.0
    return base + bonus


def format_band(band: float | None) -> str:
    """
    Formats a band float for display.
    None → "No band yet"
    5.0  → "Band 5.0"
    6.5  → "Band 6.5"
    """
    if band is None:
        return "No band yet"
    return f"Band {band:.1f}"


def get_band_label(band: float | None) -> str:
    """
    Returns a descriptive label for a band estimate.
    Used in the UI alongside the band number.
    """
    if band is None:
        return "Complete a practice session to see your band"

    if band < 4.5:
        return "Emerging"
    elif band < 5.5:
        return "Developing"
    elif band < 6.5:
        return "Competent"
    elif band < 7.5:
        return "Proficient"
    elif band < 8.5:
        return "Advanced"
    else:
        return "Expert"


# ─── Taxonomy loading ─────────────────────────────────────────────────────────

def load_taxonomy(section: str = "Writing") -> dict:
    """
    Loads the skill taxonomy for a given section.
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
    Used when building the fixed-list prompt for Qwen —
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
                return {
                    **skill,
                    "category_id": category["category_id"],
                    "category_name": category["category_name"]
                }
    return None


def get_skills_flat(section: str = "Writing") -> list:
    """
    Returns every skill as a flat list with category info attached.
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
    Kept for backward compatibility with Coach agent and MCP server.
    """
    return RANK_NAMES.get(rank, "Unknown")


def format_skill_list_for_prompt(section: str = "Writing") -> str:
    """
    Builds a formatted text block listing every skill_id and its
    description. Injected into Qwen prompts so Qwen can only
    choose from this fixed list.
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
    given rank. Used when generating teaching content in the
    Chat Coach — the lesson explains what THIS rank and the
    NEXT rank look like.
    """
    skill = get_skill_by_id(skill_id, section)
    if not skill:
        return ""
    return skill["ranks"].get(str(rank), "")


# ─── BRIDGING TO THE FREE-TEXT MEMORY SYSTEM ──────────────────────────────────

SKILL_ID_TO_MEMORY_LABELS = {
    # Writing
    "tr_full_coverage":          ["Task Response", "Idea Development"],
    "tr_position_clarity":       ["Thesis Clarity"],
    "tr_idea_development":       ["Idea Development"],
    "tr_conclusion_synthesis":   ["Conclusion", "Thesis Clarity"],
    "cc_logical_progression":    ["Organization"],
    "cc_paragraphing":           ["Organization"],
    "cc_cohesive_devices":       ["Organization", "Grammar"],
    "lr_range":                  ["Vocabulary"],
    "lr_precision":              ["Vocabulary"],
    "lr_spelling_word_formation": ["Vocabulary", "Grammar"],
    "gra_sentence_variety":      ["Grammar"],
    "gra_accuracy":              ["Grammar"],
    "gra_punctuation":           ["Grammar"],
    # Reading
    "ri_detail_retrieval":       ["Detail Retrieval"],
    "ri_skimming":               ["Main Idea", "Skimming"],
    "ri_scanning":               ["Detail Retrieval", "Scanning"],
    "rc_main_idea":              ["Main Idea"],
    "rc_inference":              ["Inference"],
    "rc_tfng":                   ["True False Not Given"],
    "rc_writer_intent":          ["Inference", "Main Idea"],
    "rv_context_meaning":        ["Vocabulary in Context"],
    "rv_paraphrase":             ["Vocabulary in Context"],
    "rt_paragraph_purpose":      ["Main Idea", "Organization"],
    # Speaking
    "sf_fluency":                ["Fluency"],
    "sf_coherence":              ["Organization", "Fluency"],
    "sf_extension":              ["Idea Development", "Fluency"],
    "sl_vocabulary_range":       ["Vocabulary", "Lexical Resource"],
    "sl_paraphrase":             ["Vocabulary", "Lexical Resource"],
    "sg_grammar_range":          ["Grammar", "Grammatical Range"],
    "sg_grammar_accuracy":       ["Grammar", "Grammatical Range"],
    "sp_intelligibility":        ["Pronunciation"],
    "sp_features":               ["Pronunciation"],
    # Listening
    "ld_detail_accuracy":        ["Detail Retrieval", "Accuracy"],
    "ld_form_completion":        ["Detail Retrieval", "Form Completion"],
    "ld_number_recognition":     ["Detail Retrieval"],
    "lm_main_idea":              ["Main Idea"],
    "lm_speaker_purpose":        ["Inference", "Main Idea"],
    "li_inference":              ["Inference"],
    "li_distractor_resistance":  ["Inference", "Detail Retrieval"],
    "ls_prediction":             ["Strategy", "Main Idea"],
}


def get_memory_labels_for_skill(skill_id: str) -> list:
    """
    Returns the free-text memory 'skill' labels most likely to
    correspond to a given fixed skill_id.
    """
    return SKILL_ID_TO_MEMORY_LABELS.get(skill_id, [])
