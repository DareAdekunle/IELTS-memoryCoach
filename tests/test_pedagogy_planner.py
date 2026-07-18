"""
Tests for deterministic routing, exit criteria, practice conditions,
fading rules, action tags, and the spine validator.
Run from repo root:  python tests/test_pedagogy_planner.py
"""
import sys
sys.path.append('.')

from app.pedagogy.stages import LearnerStage, SupportLevel
from app.pedagogy.planner import (
    select_framework, exit_criteria_for,
)
from app.pedagogy.session_policy import conditions_for
from app.pedagogy.fading import (
    should_reduce_support, should_restore_support, evaluate_support_change,
)
from app.pedagogy.action_tags import parse_action_tags
from app.pedagogy.spine import validate_spine, validate_triad

print("=== Test 1: Routing tests (spec §25.1) ===")
# Band 5 Writing + unfamiliar task type → Genre-Based Pedagogy
assert select_framework(
    "Writing", "task_response", LearnerStage.FOUNDATIONS,
    unfamiliar_task_type=True
) == "genre_based_pedagogy"

# Band 6 Writing + recurring grammar errors → Focused Indirect Feedback
assert select_framework(
    "Writing", "grammatical_range_accuracy", LearnerStage.GUIDED_CONTROL
) == "focused_indirect_feedback"

# Band 7 Reading → Gradual Release (timed independent sections)
assert select_framework(
    "Reading", "rt", LearnerStage.INDEPENDENT_CONTROL
) == "gradual_release_of_responsibility"

# Band 5 Listening + decoding failure → Micro-Listening and Dictation
assert select_framework(
    "Listening", "ld", LearnerStage.FOUNDATIONS
) == "micro_listening_dictation"

# Band 7 Speaking + limited lexical range → Reformulation
assert select_framework(
    "Speaking", "sl", LearnerStage.INDEPENDENT_CONTROL
) == "reformulation"

# Writing structure at Foundations → genre; at Guided → process
assert select_framework(
    "Writing", "coherence_cohesion", LearnerStage.FOUNDATIONS
) == "genre_based_pedagogy"
assert select_framework(
    "Writing", "coherence_cohesion", LearnerStage.GUIDED_CONTROL
) == "process_writing"
print("✅ All 5 spec routing scenarios pass\n")

print("=== Test 2: Exit criteria tighten with stage ===")
f = exit_criteria_for(LearnerStage.FOUNDATIONS)
a = exit_criteria_for(LearnerStage.AUTOMATIZATION)
assert f["maximum_hint_level"] > a["maximum_hint_level"]
assert f["minimum_accuracy"] < a["minimum_accuracy"]
assert not f["timed_transfer_required"] and a["timed_transfer_required"]
print("✅ Exit criteria tighten correctly\n")

print("=== Test 3: Condition gates switch at stages ===")
w_found = conditions_for("Writing", LearnerStage.FOUNDATIONS)
w_guided = conditions_for("Writing", LearnerStage.GUIDED_CONTROL)
w_indep = conditions_for("Writing", LearnerStage.INDEPENDENT_CONTROL)
assert not w_found.revision_required and w_guided.revision_required
assert not w_guided.timed and w_indep.timed
assert w_found.templates_allowed and not w_indep.templates_allowed

l_found = conditions_for("Listening", LearnerStage.FOUNDATIONS)
l_guided = conditions_for("Listening", LearnerStage.GUIDED_CONTROL)
l_indep = conditions_for("Listening", LearnerStage.INDEPENDENT_CONTROL)
assert l_found.replay_limit is None          # unlimited
assert l_guided.replay_limit == 2
assert l_indep.replay_limit == 1             # single play
assert l_found.transcript_policy == "during"
assert l_indep.transcript_policy == "review_only"
print("✅ Condition gates correct (untimed→timed, replay limits, transcripts)\n")

print("=== Test 4: Fading rules (spec §25.3) ===")
# Repeated independent success → support decreases
assert should_reduce_support(3, 0.8, 0.85) is True
# Not enough successes
assert should_reduce_support(2, 0.5, 0.9) is False
# Too hint-dependent
assert should_reduce_support(5, 2.0, 0.9) is False
# Performance collapse after reduction → restore
assert should_restore_support(2, "reduced") is True
assert should_restore_support(2, None) is False
assert should_restore_support(1, "reduced") is False

# Guardrail: unearned reduction is vetoed
r = evaluate_support_change(
    current_level=SupportLevel.PARTIAL,
    requested_level=SupportLevel.NONE,
    recent_successes=1, average_hint_level=3.0,
    independent_accuracy=0.4, recent_failures=0,
    last_support_change=None,
)
assert r["allowed"] is False
assert r["final_level"] == "partial"

# Earned reduction is one step only (partial → minimal, not none)
r = evaluate_support_change(
    current_level=SupportLevel.PARTIAL,
    requested_level=SupportLevel.NONE,
    recent_successes=4, average_hint_level=0.5,
    independent_accuracy=0.9, recent_failures=0,
    last_support_change=None,
)
assert r["allowed"] is True
assert r["final_level"] == "minimal", "must fade one step at a time"

# Restoration always allowed, one step
r = evaluate_support_change(
    current_level=SupportLevel.MINIMAL,
    requested_level=SupportLevel.FULL,
    recent_successes=0, average_hint_level=4.0,
    independent_accuracy=0.2, recent_failures=3,
    last_support_change="reduced",
)
assert r["allowed"] is True
assert r["final_level"] == "partial", "restore one step at a time"
print("✅ Fading rules + one-step guardrails correct\n")

print("=== Test 5: Action tag parser ===")
text = """Good attempt! [ACTION: attempt result=self_corrected]
You fixed the verb agreement yourself.

Now try this one. [ACTION: hint level=2]
Look at whether the subject is singular.

[STATE: drilling]"""
clean, actions = parse_action_tags(text)
assert "[ACTION" not in clean
assert len(actions) == 2
assert actions[0] == {"action": "attempt", "params": {"result": "self_corrected"}}
assert actions[1] == {"action": "hint", "params": {"level": 2}}
assert "[STATE: drilling]" in clean  # state tag untouched

# Malformed tags dropped silently
clean, actions = parse_action_tags("[ACTION: hint level=9] [ACTION: bogus] [ACTION: attempt result=maybe]")
assert actions == [], f"malformed tags must be dropped, got {actions}"

# Complete with outcome
_, actions = parse_action_tags("[ACTION: complete outcome=ready_for_reduced_support]")
assert actions[0]["params"]["outcome"] == "ready_for_reduced_support"

# Formatting drift tolerance — real Qwen output uses spaces inside brackets
drifted = "[ ACTION: model_shown ]\n[ ACTION: hint level = 2 ]\nHere are two excerpts..."
clean, actions = parse_action_tags(drifted)
assert "ACTION" not in clean, f"drifted tags must strip: {clean[:80]}"
assert len(actions) == 2
assert actions[1] == {"action": "hint", "params": {"level": 2}}

# State tag drift + action tag AFTER state tag
from app.services.chat_coach_service import parse_state_tag
text = "Great work!\n[ STATE : drilling ]\n[ ACTION: attempt result=success ]"
clean, state = parse_state_tag(text)
assert state == "drilling"
assert "STATE" not in clean
clean2, acts = parse_action_tags(clean)
assert len(acts) == 1 and acts[0]["action"] == "attempt"
print("✅ Action tags parse, validate, strip — including drifted formatting\n")

print("=== Test 6: Spine validator (soft) ===")
good = """Here is my feedback on your essay. Your goal is Band 7 grammar —
frequent error-free sentences. Right now, your last paragraph has two
relative clauses with verb-agreement errors. Next step: can you find and
correct just those two clauses before we continue?"""
r = validate_spine(good)
assert r["is_feedback"] is True
assert r["passed"] is True, f"triad legs: {r['triad']}"

bad = """Your essay has problems with grammar. There are also issues with
vocabulary and your paragraphs. You made 12 errors in this essay overall
and the introduction was weak too. The conclusion needs work as well."""
r = validate_spine(bad)
assert r["is_feedback"] is True
assert r["passed"] is False
assert r["retry_nudge"] is not None

short = "Great, let's move on!"
r = validate_spine(short)
assert r["is_feedback"] is False and r["passed"] is True
print("✅ Spine validator distinguishes triad from non-triad feedback\n")

print("ALL PLANNER TESTS PASSED")
