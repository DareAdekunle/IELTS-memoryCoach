"""
Integration test: session → plan → events → hint dependency →
criterion state → Coach guardrail, against the real SQLite schema.
Run from repo root:  python tests/test_pedagogy_integration.py
"""
import sys
sys.path.append('.')

import json
from app.db.database import engine, SessionLocal, Base
import app.db.models  # register all models
from app.db.models import (
    TutorSession, TutorSessionPlan, PedagogicalEvent, HintEvent,
    LearnerCriterionState,
)

Base.metadata.create_all(bind=engine)

TEST_LEARNER = "test_learner_pedagogy"
SECTION = "Writing"


def cleanup():
    db = SessionLocal()
    try:
        for model in (TutorSession, TutorSessionPlan, PedagogicalEvent,
                      HintEvent, LearnerCriterionState):
            db.query(model).filter(
                model.learner_id == TEST_LEARNER
            ).delete()
        db.commit()
    finally:
        db.close()


cleanup()

from app.services.pedagogical_event_service import (
    create_tutor_session, update_session_state, record_event, record_hint,
    mark_last_hint_self_corrected, get_session_events, get_session_hints,
    get_hint_dependency, summarize_session_evidence, get_session_plan,
    complete_session_plan,
)
from app.pedagogy.stage_resolver import (
    get_criterion_bands, resolve_criterion, upsert_criterion_state,
    get_criterion_state_row, get_all_criterion_stages,
)

print("=== Test 1: Tutor session lifecycle ===")
session_id = create_tutor_session(TEST_LEARNER, SECTION)
assert session_id and len(session_id) == 12
update_session_state(session_id, "drilling")
update_session_state(session_id, "bridge_to_practice")
db = SessionLocal()
row = db.query(TutorSession).filter(TutorSession.session_id == session_id).first()
assert row.state == "bridge_to_practice"
assert row.completed_at is not None
db.close()
print("✅ Session created, state tracked, completion stamped\n")

print("=== Test 2: Cold-start criterion resolution ===")
bands = get_criterion_bands(TEST_LEARNER, SECTION)
assert set(bands.keys()) == {
    "task_response", "coherence_cohesion",
    "lexical_resource", "grammatical_range_accuracy"
}
assert all(b is None for b in bands.values()), "no evidence → no bands"
crit = resolve_criterion(TEST_LEARNER, SECTION, "grammatical_range_accuracy")
assert crit["stage"] == "foundations"          # cold start default
assert crit["support_level"] == "full"          # foundations default
assert crit["target_band"] == 5.0
assert crit["target_descriptor"]
print("✅ Cold start resolves to Foundations + full support\n")

print("=== Test 3: Events + hints recorded and queried ===")
record_event(session_id, TEST_LEARNER, SECTION, "framework_started",
             criterion_id="grammatical_range_accuracy",
             framework_id="focused_indirect_feedback")
record_hint(session_id, TEST_LEARNER, SECTION, 2,
            criterion_id="grammatical_range_accuracy")
record_event(session_id, TEST_LEARNER, SECTION, "self_correction_succeeded",
             criterion_id="grammatical_range_accuracy", success=True)
mark_last_hint_self_corrected(session_id, True)
record_hint(session_id, TEST_LEARNER, SECTION, 1,
            criterion_id="grammatical_range_accuracy")
record_event(session_id, TEST_LEARNER, SECTION, "learner_attempted",
             criterion_id="grammatical_range_accuracy", success=True)
mark_last_hint_self_corrected(session_id, True)
record_event(session_id, TEST_LEARNER, SECTION, "independent_check_started",
             criterion_id="grammatical_range_accuracy")

events = get_session_events(session_id)
hints = get_session_hints(session_id)
assert len(events) == 4
assert len(hints) == 2
assert all(h["self_corrected"] is True for h in hints)

dep = get_hint_dependency(TEST_LEARNER, SECTION)
assert dep["hint_count"] == 2
assert dep["average_hint_level"] == 1.5
assert dep["self_correction_rate"] == 1.0

summary = summarize_session_evidence(session_id)
assert summary["hints_given"] == 2
assert summary["highest_hint_level"] == 2
assert summary["self_corrections_succeeded"] == 1
assert summary["independent_checks"] == 1
print("✅ Events, hints, dependency metrics, session summary all correct\n")

print("=== Test 4: Criterion state upsert + support guardrail ===")
r = upsert_criterion_state(
    TEST_LEARNER, SECTION, "grammatical_range_accuracy",
    hint_dependency_score=1.5, independent_success_count=2,
)
assert r["updated"]
state = get_criterion_state_row(TEST_LEARNER, SECTION, "grammatical_range_accuracy")
assert state["exists"] and state["independent_success_count"] == 2

# Coach tool guardrail via executor
from app.services.agent_tools import execute_coach_tool
result = json.loads(execute_coach_tool("update_criterion_state", {
    "learner_id": TEST_LEARNER,
    "section": SECTION,
    "criterion_id": "grammatical_range_accuracy",
    "requested_support_level": "none",     # greedy request
    "recent_successes": 1,                  # insufficient evidence
    "average_hint_level": 3.0,
    "independent_accuracy": 0.3,
}))
assert result["support_change"]["allowed"] is False, "unearned reduction must be vetoed"

result = json.loads(execute_coach_tool("update_criterion_state", {
    "learner_id": TEST_LEARNER,
    "section": SECTION,
    "criterion_id": "grammatical_range_accuracy",
    "requested_support_level": "partial",
    "recent_successes": 4,
    "average_hint_level": 0.8,
    "independent_accuracy": 0.9,
    "independent_successes": 1,
}))
assert result["support_change"]["allowed"] is True
assert result["support_change"]["final_level"] == "partial"
state = get_criterion_state_row(TEST_LEARNER, SECTION, "grammatical_range_accuracy")
assert state["support_level"] == "partial"
assert state["last_support_change"] == "reduced"
assert state["independent_success_count"] == 3
print("✅ Criterion state + deterministic support guardrail work end-to-end\n")

print("=== Test 5: Planner creates and persists a full plan ===")
# Needs a weakest skill — give the learner one classified skill first
from app.services.memory_service import apply_skill_classification
apply_skill_classification(
    TEST_LEARNER, SECTION, "gra_accuracy", "demonstrated_weakness"
)
from app.pedagogy.planner import create_session_plan, format_plan_block
session_id2 = create_tutor_session(TEST_LEARNER, SECTION)
plan = create_session_plan(TEST_LEARNER, SECTION, session_id2)
assert plan is not None
assert plan.section == SECTION
assert plan.target_criterion in {
    "task_response", "coherence_cohesion",
    "lexical_resource", "grammatical_range_accuracy"
}
assert plan.dominant_framework
assert plan.exit_criteria["maximum_hint_level"] >= 1
assert isinstance(plan.practice_conditions, dict)

stored = get_session_plan(session_id2)
assert stored and stored["dominant_framework"] == plan.dominant_framework

block = format_plan_block(plan)
assert "PEDAGOGICAL SESSION PLAN" in block
assert "SHARED TEACHING HABITS" in block
assert plan.target_descriptor[:30] in block

complete_session_plan(session_id2, "completed")
stored = get_session_plan(session_id2)
assert stored["outcome"] == "completed"
print("✅ Plan created, persisted, formatted, completed\n")

print("=== Test 6: get_all_criterion_stages returns 4 criteria ===")
stages = get_all_criterion_stages(TEST_LEARNER, SECTION)
assert len(stages) == 4
gra = next(s for s in stages if s["criterion_id"] == "grammatical_range_accuracy")
assert gra["band"] is not None, "classified skill should produce a band"
assert gra["support_level"] == "partial", "Coach-set level wins over stage default"
print("✅ Criterion stages aggregate correctly\n")

cleanup()
# Clean up the rank row created in test 5
db = SessionLocal()
from app.db.models import LearnerSkillRank
db.query(LearnerSkillRank).filter(
    LearnerSkillRank.learner_id == TEST_LEARNER
).delete()
db.commit()
db.close()

print("ALL INTEGRATION TESTS PASSED")
