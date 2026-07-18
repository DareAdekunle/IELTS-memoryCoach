"""
app/pedagogy/stage_resolver.py

Derives per-criterion bands and learner stages from the existing
skill-rank system. Nothing here is stored — learner_skill_ranks is
the single source of truth for bands; this module aggregates it.

Criterion == taxonomy category. Each skill in the taxonomy belongs
to exactly one category, and Writing categories map 1:1 onto the
official IELTS criteria.

Pedagogy-only state (support level, hint dependency, success
counters) lives in learner_criterion_state and is merged in here.
"""

import uuid

from app.db.database import SessionLocal
from app.db.models import LearnerCriterionState
from app.pedagogy.stages import (
    LearnerStage,
    SupportLevel,
    band_to_stage,
    DEFAULT_SUPPORT_BY_STAGE,
    STAGE_LABELS,
    STAGE_BOTTLENECKS,
)
from app.pedagogy.descriptors import (
    get_descriptor,
    get_target_descriptor,
    get_criterion_name,
)


def get_criterion_bands(learner_id: str, section: str) -> dict:
    """
    Aggregates skill-level band estimates into per-criterion bands.

    Returns {criterion_id: band | None} — None when no skill in the
    criterion has any evidence yet (cold start).
    """
    from app.services.memory_service import get_all_skill_ranks
    from app.services.skill_taxonomy_service import get_skills_flat

    skills_by_criterion = {}
    for skill in get_skills_flat(section):
        skills_by_criterion.setdefault(skill["category_id"], []).append(
            skill["skill_id"]
        )

    ranks = {r["skill_id"]: r for r in get_all_skill_ranks(learner_id, section)}

    bands = {}
    for criterion_id, skill_ids in skills_by_criterion.items():
        with_evidence = [
            ranks[sid]["band"] for sid in skill_ids
            if sid in ranks and ranks[sid].get("band") is not None
        ]
        if with_evidence:
            # Round to nearest 0.5 to stay on the band scale
            avg = sum(with_evidence) / len(with_evidence)
            bands[criterion_id] = round(avg * 2) / 2
        else:
            bands[criterion_id] = None

    return bands


def get_criterion_state_row(
    learner_id: str,
    section: str,
    criterion_id: str
) -> dict:
    """
    Reads the pedagogy-only state row for a criterion.
    Returns defaults when no row exists yet.
    """
    db = SessionLocal()
    try:
        row = db.query(LearnerCriterionState).filter(
            LearnerCriterionState.learner_id == learner_id,
            LearnerCriterionState.section == section,
            LearnerCriterionState.criterion_id == criterion_id,
        ).first()

        if not row:
            return {
                "exists": False,
                "support_level": None,
                "hint_dependency_score": 0.0,
                "independent_success_count": 0,
                "timed_success_count": 0,
                "last_support_change": None,
            }
        return {
            "exists": True,
            "support_level": row.support_level,
            "hint_dependency_score": row.hint_dependency_score,
            "independent_success_count": row.independent_success_count,
            "timed_success_count": row.timed_success_count,
            "last_support_change": row.last_support_change,
        }
    finally:
        db.close()


def upsert_criterion_state(
    learner_id: str,
    section: str,
    criterion_id: str,
    **fields
) -> dict:
    """
    Creates or updates the pedagogy state row for a criterion.
    Accepted fields: support_level, hint_dependency_score,
    independent_success_count, timed_success_count, last_support_change.
    """
    allowed = {
        "support_level", "hint_dependency_score",
        "independent_success_count", "timed_success_count",
        "last_support_change",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}

    db = SessionLocal()
    try:
        row = db.query(LearnerCriterionState).filter(
            LearnerCriterionState.learner_id == learner_id,
            LearnerCriterionState.section == section,
            LearnerCriterionState.criterion_id == criterion_id,
        ).first()

        if not row:
            row = LearnerCriterionState(
                state_id=str(uuid.uuid4())[:12],
                learner_id=learner_id,
                section=section,
                criterion_id=criterion_id,
            )
            db.add(row)

        for k, v in updates.items():
            setattr(row, k, v)

        db.commit()
        return {"updated": True, "criterion_id": criterion_id, **updates}
    except Exception as e:
        db.rollback()
        return {"updated": False, "error": str(e)}
    finally:
        db.close()


def resolve_criterion(
    learner_id: str,
    section: str,
    criterion_id: str,
    band: float | None = None
) -> dict:
    """
    Full pedagogical picture for one criterion: band, stage, support
    level, descriptors, and evidence counters.
    """
    if band is None:
        band = get_criterion_bands(learner_id, section).get(criterion_id)

    stage = band_to_stage(band)
    state = get_criterion_state_row(learner_id, section, criterion_id)

    # Coach-set support level wins; otherwise stage default
    if state["support_level"]:
        support = SupportLevel(state["support_level"])
    else:
        support = DEFAULT_SUPPORT_BY_STAGE[stage]

    target_band, target_text = get_target_descriptor(section, criterion_id, band)

    return {
        "criterion_id": criterion_id,
        "criterion_name": get_criterion_name(section, criterion_id),
        "band": band,
        "stage": stage.value,
        "stage_label": STAGE_LABELS[stage],
        "bottleneck": STAGE_BOTTLENECKS[stage],
        "support_level": support.value,
        "current_descriptor": get_descriptor(section, criterion_id, band),
        "target_band": target_band,
        "target_descriptor": target_text,
        "hint_dependency_score": state["hint_dependency_score"],
        "independent_success_count": state["independent_success_count"],
        "timed_success_count": state["timed_success_count"],
    }


def get_all_criterion_stages(learner_id: str, section: str) -> list:
    """Resolved pedagogical state for every criterion in a section."""
    bands = get_criterion_bands(learner_id, section)
    return [
        resolve_criterion(learner_id, section, cid, band)
        for cid, band in bands.items()
    ]
