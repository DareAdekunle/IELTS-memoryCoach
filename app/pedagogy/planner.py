"""
app/pedagogy/planner.py

The Pedagogy Planner — deterministic framework routing and session
plan generation.

Python selects the teaching method; Qwen generates and delivers the
teaching. The model never controls: stage transitions, framework
eligibility, feedback priority caps, hint escalation order, timing
gates, or rank progression.

Routing precedence per section:
  1. Skill/criterion-specific overrides (e.g. grammar errors →
     Focused Indirect Corrective Feedback regardless of stage)
  2. Stage-dominant framework from the registry
  3. Section fallback
"""

import json
import uuid
from dataclasses import dataclass, field, asdict

from app.db.database import SessionLocal
from app.db.models import TutorSessionPlan
from app.pedagogy.stages import LearnerStage, SupportLevel
from app.pedagogy.registry import (
    get_dominant_frameworks,
    get_supporting_frameworks,
    get_framework,
)
from app.pedagogy.stage_resolver import resolve_criterion
from app.pedagogy.session_policy import conditions_for
from app.utils.logger import get_logger

logger = get_logger("pedagogy.planner")

MAX_FEEDBACK_PRIORITIES = 2


@dataclass
class PedagogyPlan:
    session_plan_id: str
    section: str
    target_skill: str
    target_skill_name: str
    target_criterion: str
    criterion_name: str
    current_band: float | None
    target_band: float
    learner_stage: str
    target_descriptor: str
    dominant_framework: str
    supporting_frameworks: list
    support_level: str
    practice_conditions: dict
    feedback_priorities: list = field(default_factory=list)
    exit_criteria: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Deterministic routing tables ────────────────────────────────────────────

def select_writing_framework(
    criterion_id: str,
    stage: LearnerStage,
    unfamiliar_task_type: bool = False,
) -> str:
    if unfamiliar_task_type:
        return "genre_based_pedagogy"

    if criterion_id in {"grammatical_range_accuracy", "lexical_resource"}:
        return "focused_indirect_feedback"

    if criterion_id in {"task_response", "coherence_cohesion"}:
        if stage == LearnerStage.FOUNDATIONS:
            return "genre_based_pedagogy"
        return "process_writing"

    return "scaffolding_with_fading"


def select_reading_framework(criterion_id: str, stage: LearnerStage) -> str:
    # Vocabulary gaps are strategy-teachable at any stage
    if criterion_id == "rv" and stage in (
        LearnerStage.FOUNDATIONS, LearnerStage.GUIDED_CONTROL
    ):
        return "explicit_strategy_instruction"

    dominant = get_dominant_frameworks("Reading", stage)
    if dominant:
        return dominant[0]
    return "error_driven_diagnosis"


def select_listening_framework(criterion_id: str, stage: LearnerStage) -> str:
    # Detail/decoding failures at low stages → dictation work
    if criterion_id == "ld" and stage == LearnerStage.FOUNDATIONS:
        return "micro_listening_dictation"

    dominant = get_dominant_frameworks("Listening", stage)
    if dominant:
        # Prefer the metacognitive cycle when it is dominant
        if "metacognitive_cycle" in dominant:
            return "metacognitive_cycle"
        return dominant[0]
    return "process_based_listening"


def select_speaking_framework(criterion_id: str, stage: LearnerStage) -> str:
    # Lexical range gaps at higher stages → reformulation
    if criterion_id == "sl" and stage in (
        LearnerStage.INDEPENDENT_CONTROL, LearnerStage.AUTOMATIZATION
    ):
        return "reformulation"

    # Grammar/pronunciation accuracy issues → oral corrective feedback
    if criterion_id in {"sg", "sp"} and stage == LearnerStage.GUIDED_CONTROL:
        return "oral_corrective_feedback"

    dominant = get_dominant_frameworks("Speaking", stage)
    if dominant:
        if "task_based_language_teaching" in dominant:
            return "task_based_language_teaching"
        return dominant[0]
    return "task_based_language_teaching"


SECTION_ROUTERS = {
    "Writing": select_writing_framework,
    "Reading": select_reading_framework,
    "Listening": select_listening_framework,
    "Speaking": select_speaking_framework,
}


def select_framework(
    section: str,
    criterion_id: str,
    stage: LearnerStage,
    unfamiliar_task_type: bool = False,
) -> str:
    router = SECTION_ROUTERS.get(section)
    if not router:
        return "scaffolding_with_fading"
    if section == "Writing":
        return router(criterion_id, stage, unfamiliar_task_type)
    return router(criterion_id, stage)


# ─── Exit criteria by stage ──────────────────────────────────────────────────

def exit_criteria_for(stage: LearnerStage) -> dict:
    """
    What successful completion of a pedagogical session looks like.
    Tightens as the learner climbs stages (Dynamic Assessment:
    hints start weaker and are withdrawn sooner).
    """
    if stage == LearnerStage.FOUNDATIONS:
        return {
            "minimum_accuracy": 0.6,
            "maximum_hint_level": 3,
            "required_independent_successes": 1,
            "timed_transfer_required": False,
        }
    if stage == LearnerStage.GUIDED_CONTROL:
        return {
            "minimum_accuracy": 0.8,
            "maximum_hint_level": 2,
            "required_independent_successes": 2,
            "timed_transfer_required": False,
        }
    if stage == LearnerStage.INDEPENDENT_CONTROL:
        return {
            "minimum_accuracy": 0.8,
            "maximum_hint_level": 1,
            "required_independent_successes": 2,
            "timed_transfer_required": True,
        }
    return {
        "minimum_accuracy": 0.9,
        "maximum_hint_level": 1,
        "required_independent_successes": 3,
        "timed_transfer_required": True,
    }


# ─── Feedback priorities ─────────────────────────────────────────────────────

def feedback_priorities_for(
    learner_id: str,
    section: str,
    criterion_id: str,
    target_descriptor: str | None = None,
) -> list:
    """
    The 2 highest-confidence weakness memories most relevant to the
    current session's target descriptor.

    Uses semantic retrieval when a target descriptor is available:
    memories semantically close to what the session is targeting float
    to the top rather than just the most recently updated ones.

    Capped at MAX_FEEDBACK_PRIORITIES — feedback overload harms learning.
    """
    from app.services.memory_service import get_relevant_memories

    # Use the target descriptor as context for semantic search
    memories = get_relevant_memories(
        learner_id, section, limit=8,
        context=target_descriptor,
    )
    weaknesses = [m for m in memories if m.get("memory_type") == "weakness"]
    return [
        {"skill": m.get("skill", ""), "evidence": m.get("memory_text", "")}
        for m in weaknesses[:MAX_FEEDBACK_PRIORITIES]
    ]


# ─── Plan creation ───────────────────────────────────────────────────────────

def create_session_plan(
    learner_id: str,
    section: str,
    session_id: str,
    unfamiliar_task_type: bool = False,
) -> PedagogyPlan | None:
    """
    Creates and persists the deterministic teaching plan for a
    Tutor session. Returns None when the learner has no assessed
    weakest skill yet (no-history welcome path).
    """
    from app.services.memory_service import get_weakest_skill
    from app.services.skill_taxonomy_service import get_skills_flat

    weakest = get_weakest_skill(learner_id, section)
    if not weakest:
        return None

    target_skill = weakest["skill_id"]

    # Which criterion (category) does this skill belong to?
    criterion_id = None
    skill_name = weakest.get("skill_name", target_skill)
    for skill in get_skills_flat(section):
        if skill["skill_id"] == target_skill:
            criterion_id = skill["category_id"]
            skill_name = skill["skill_name"]
            break
    if criterion_id is None:
        logger.warning(f"Skill {target_skill} not found in {section} taxonomy")
        return None

    crit = resolve_criterion(learner_id, section, criterion_id)
    stage = LearnerStage(crit["stage"])

    dominant = select_framework(
        section, criterion_id, stage, unfamiliar_task_type
    )
    supporting = [
        fw for fw in get_supporting_frameworks(section, stage)
        if fw != dominant
    ][:2]

    conditions = conditions_for(section, stage)

    plan = PedagogyPlan(
        session_plan_id=str(uuid.uuid4())[:12],
        section=section,
        target_skill=target_skill,
        target_skill_name=skill_name,
        target_criterion=criterion_id,
        criterion_name=crit["criterion_name"],
        current_band=crit["band"],
        target_band=crit["target_band"],
        learner_stage=stage.value,
        target_descriptor=crit["target_descriptor"],
        dominant_framework=dominant,
        supporting_frameworks=supporting,
        support_level=crit["support_level"],
        practice_conditions=conditions.to_dict(),
        feedback_priorities=feedback_priorities_for(
            learner_id, section, criterion_id,
            target_descriptor=crit.get("target_descriptor"),
        ),
        exit_criteria=exit_criteria_for(stage),
    )

    # Persist
    db = SessionLocal()
    try:
        row = TutorSessionPlan(
            session_plan_id=plan.session_plan_id,
            session_id=session_id,
            learner_id=learner_id,
            section=section,
            target_skill=plan.target_skill,
            target_criterion=plan.target_criterion,
            target_descriptor=plan.target_descriptor,
            current_stage=plan.learner_stage,
            dominant_framework=plan.dominant_framework,
            supporting_frameworks_json=json.dumps(plan.supporting_frameworks),
            support_level=plan.support_level,
            practice_conditions_json=json.dumps(plan.practice_conditions),
            feedback_priorities_json=json.dumps(plan.feedback_priorities),
            exit_criteria_json=json.dumps(plan.exit_criteria),
        )
        db.add(row)
        db.commit()
        logger.info(
            f"pedagogy_plan_created learner={learner_id} section={section} "
            f"criterion={criterion_id} stage={stage.value} "
            f"framework={dominant} support={plan.support_level}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to persist session plan: {e}")
    finally:
        db.close()

    return plan


def format_plan_block(plan: PedagogyPlan) -> str:
    """
    Formats the plan as the structured block injected into the Tutor
    system prompt (spec §23). The model carries out the plan
    naturally — it does not redefine it.
    """
    fw = get_framework(plan.dominant_framework)
    fw_name = fw["name"] if fw else plan.dominant_framework
    fw_purpose = fw["purpose"] if fw else ""
    fw_procedure = "\n".join(f"  {i+1}. {step.replace('_', ' ')}"
                             for i, step in enumerate(fw["procedure"])) if fw else ""

    supporting_names = []
    for sid in plan.supporting_frameworks:
        sfw = get_framework(sid)
        supporting_names.append(sfw["name"] if sfw else sid)

    priorities = "\n".join(
        f"  - {p['skill']}: {p['evidence']}"
        for p in plan.feedback_priorities
    ) or "  - (no recorded weakness memories yet — observe and diagnose)"

    band_display = (
        f"{plan.current_band:.1f}" if plan.current_band is not None
        else "no evidence yet"
    )

    return f"""
## PEDAGOGICAL SESSION PLAN (follow this — do not redefine it)

Target skill: {plan.target_skill_name}
Target criterion: {plan.criterion_name}
Current band: {band_display} → Target band: {plan.target_band:.1f}
Learner stage: {plan.learner_stage.replace('_', ' ').title()}

Target descriptor (Backward Design — every activity aims here):
"{plan.target_descriptor}"

Dominant teaching method: {fw_name}
Purpose: {fw_purpose}
Procedure:
{fw_procedure}

Supporting methods: {', '.join(supporting_names) or 'none'}
Support level: {plan.support_level.upper()}
  full    = models, templates, sentence frames, direct explanation
  partial = planning prompts, guided questions, selected hints
  minimal = vague prompts, hints only after failure
  none    = independent performance under exam conditions

Feedback priorities (NEVER exceed {MAX_FEEDBACK_PRIORITIES} per feedback message):
{priorities}

Exit criteria for this session:
{json.dumps(plan.exit_criteria, indent=2)}

## SHARED TEACHING HABITS (every reply, every stage)
1. Backward Design — anchor every activity to the target descriptor above.
2. Feedback Triad — significant feedback states: the GOAL, the learner's
   CURRENT position, and ONE concrete NEXT STEP.
3. Dynamic Assessment — weakest hint first (level 1 = vague nudge,
   level 4 = full answer). Escalate ONE level at a time, only if needed.
4. Elicitation Before Telling — the learner attempts, identifies, or
   repairs BEFORE you reveal any answer.
"""
