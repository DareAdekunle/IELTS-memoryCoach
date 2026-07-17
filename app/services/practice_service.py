import json
import random
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_writing_prompts() -> list:
    path = os.path.join(DATA_DIR, "writing_prompts.json")
    with open(path, "r") as f:
        return json.load(f)


def get_random_writing_prompt() -> dict:
    """Returns a single random writing prompt (fallback — no learner context)."""
    prompts = load_writing_prompts()
    return random.choice(prompts)


def get_adaptive_writing_prompt(learner_id: str) -> dict:
    """
    Returns a writing prompt matched to the learner's current band level.

    Band → difficulty mapping:
      No band yet / Band < 5.5  → beginner
      Band 5.5 – 6.9            → intermediate
      Band 7.0+                 → advanced

    Falls back to intermediate if no band data exists.
    """
    difficulty = _get_adaptive_difficulty(learner_id, "Writing")
    return _get_prompt_by_difficulty(difficulty)


def _get_prompt_by_difficulty(difficulty: str) -> dict:
    prompts = load_writing_prompts()
    filtered = [p for p in prompts if p.get("difficulty") == difficulty]
    if not filtered:
        filtered = prompts  # fallback to all prompts
    return random.choice(filtered)


def get_writing_prompt_by_id(prompt_id: str) -> dict | None:
    prompts = load_writing_prompts()
    for prompt in prompts:
        if prompt["prompt_id"] == prompt_id:
            return prompt
    return None


def get_prompts_by_difficulty(difficulty: str) -> list:
    prompts = load_writing_prompts()
    return [p for p in prompts if p.get("difficulty") == difficulty]


def load_rubric(section: str) -> dict:
    path = os.path.join(DATA_DIR, "rubrics.json")
    with open(path, "r") as f:
        rubrics = json.load(f)
    return rubrics.get(section, {})


def get_rubric_summary(section: str) -> str:
    rubric = load_rubric(section)
    if not rubric:
        return ""

    lines = []
    skills = rubric.get("skills", {})
    max_score = rubric.get("max_score_per_skill", 5)

    for skill_key, skill_data in skills.items():
        lines.append(
            f"- {skill_data['name']} (max {max_score} points): "
            f"{skill_data['description']}"
        )

    return "\n".join(lines)


# ─── Shared adaptive difficulty engine ───────────────────────────────────────

def _get_adaptive_difficulty(learner_id: str, section: str) -> str:
    """
    Returns 'beginner', 'intermediate', or 'advanced' based on the
    learner's average band for the given section.

    Falls back to 'intermediate' if no band data exists yet.

    Band thresholds:
      < 5.5   → beginner
      5.5-6.9 → intermediate
      7.0+    → advanced
    """
    try:
        from app.services.memory_service import get_all_skill_ranks
        ranks = get_all_skill_ranks(learner_id, section)
        assessed = [r for r in ranks if r.get("total_evidence", 0) > 0]

        if not assessed:
            return "intermediate"

        valid_bands = [
            r["band"] for r in assessed
            if r.get("band") is not None
        ]

        if not valid_bands:
            return "intermediate"

        avg_band = sum(valid_bands) / len(valid_bands)

        if avg_band < 5.5:
            return "beginner"
        elif avg_band < 7.0:
            return "intermediate"
        else:
            return "advanced"

    except Exception:
        return "intermediate"


def get_adaptive_difficulty(learner_id: str, section: str) -> str:
    """Public API — returns adaptive difficulty for any section."""
    return _get_adaptive_difficulty(learner_id, section)


# ─── Seen content tracking ────────────────────────────────────────────────────

def mark_content_seen(learner_id: str, section: str, content_id: str) -> None:
    """Records that a learner has seen a specific content item."""
    try:
        import uuid
        from app.db.database import SessionLocal
        from app.db.models import LearnerSeenContent
        db = SessionLocal()
        try:
            # Only insert if not already recorded
            existing = db.query(LearnerSeenContent).filter(
                LearnerSeenContent.learner_id == learner_id,
                LearnerSeenContent.section == section,
                LearnerSeenContent.content_id == content_id
            ).first()
            if not existing:
                db.add(LearnerSeenContent(
                    seen_id=str(uuid.uuid4())[:12],
                    learner_id=learner_id,
                    section=section,
                    content_id=content_id
                ))
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass  # Never block content serving due to tracking failure


def get_seen_content_ids(learner_id: str, section: str) -> set:
    """Returns the set of content_ids already seen by this learner."""
    try:
        from app.db.database import SessionLocal
        from app.db.models import LearnerSeenContent
        db = SessionLocal()
        try:
            rows = db.query(LearnerSeenContent).filter(
                LearnerSeenContent.learner_id == learner_id,
                LearnerSeenContent.section == section
            ).all()
            return {r.content_id for r in rows}
        finally:
            db.close()
    except Exception:
        return set()


def _get_unseen_or_cycle(items: list, learner_id: str,
                          section: str, id_field: str) -> dict:
    """
    Returns an unseen item from the list.
    If all items have been seen, resets (cycles back) and picks any.
    """
    seen = get_seen_content_ids(learner_id, section)
    unseen = [i for i in items if i.get(id_field) not in seen]
    if unseen:
        return random.choice(unseen)
    # All seen — cycle back
    return random.choice(items)


def get_adaptive_writing_prompt(learner_id: str) -> dict:
    """
    Returns an unseen writing prompt matched to the learner's band level.
    Cycles back through seen prompts only when all at the level are exhausted.
    """
    difficulty = _get_adaptive_difficulty(learner_id, "Writing")
    prompts = load_writing_prompts()
    filtered = [p for p in prompts if p.get("difficulty") == difficulty]
    if not filtered:
        filtered = prompts
    return _get_unseen_or_cycle(filtered, learner_id, "Writing", "prompt_id")
