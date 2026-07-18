"""
Tests for the pedagogical framework registry, stages, and descriptors.
Run from repo root:  python tests/test_pedagogy_registry.py
"""
import sys
sys.path.append('.')

from app.pedagogy.stages import (
    LearnerStage, SupportLevel, band_to_stage,
    reduce_support, restore_support, DEFAULT_SUPPORT_BY_STAGE,
)
from app.pedagogy.registry import (
    get_framework, get_frameworks_for_section, get_framework_role,
    get_dominant_frameworks, get_supporting_frameworks,
    get_shared_spine, get_all_framework_ids,
)
from app.pedagogy.descriptors import (
    get_descriptor, get_target_descriptor, get_criterion_ids,
)
from app.pedagogy.stages import FrameworkRole

print("=== Test 1: band_to_stage boundaries ===")
assert band_to_stage(None) == LearnerStage.FOUNDATIONS, "cold start → Foundations"
assert band_to_stage(4.0) == LearnerStage.FOUNDATIONS
assert band_to_stage(5.5) == LearnerStage.FOUNDATIONS
assert band_to_stage(6.0) == LearnerStage.GUIDED_CONTROL
assert band_to_stage(6.5) == LearnerStage.INDEPENDENT_CONTROL
assert band_to_stage(7.0) == LearnerStage.INDEPENDENT_CONTROL
assert band_to_stage(7.5) == LearnerStage.AUTOMATIZATION
assert band_to_stage(9.0) == LearnerStage.AUTOMATIZATION
print("✅ Stage boundaries correct\n")

print("=== Test 2: 16 frameworks, 4 per section ===")
all_ids = get_all_framework_ids()
assert len(all_ids) == 16, f"Expected 16 frameworks, got {len(all_ids)}"
for section in ["Writing", "Reading", "Listening", "Speaking"]:
    fws = get_frameworks_for_section(section)
    assert len(fws) == 4, f"{section}: expected 4, got {len(fws)}"
print("✅ 16 frameworks, 4 per section\n")

print("=== Test 3: Roles match integrated_frameworks_by_band.md ===")
# Writing
assert get_framework_role("genre_based_pedagogy", LearnerStage.FOUNDATIONS) == FrameworkRole.DOMINANT
assert get_framework_role("genre_based_pedagogy", LearnerStage.AUTOMATIZATION) == FrameworkRole.RETIRED
assert get_framework_role("process_writing", LearnerStage.GUIDED_CONTROL) == FrameworkRole.DOMINANT
assert get_framework_role("process_writing", LearnerStage.INDEPENDENT_CONTROL) == FrameworkRole.DOMINANT
assert get_framework_role("focused_indirect_feedback", LearnerStage.GUIDED_CONTROL) == FrameworkRole.DOMINANT
# Reading
assert get_framework_role("explicit_strategy_instruction", LearnerStage.FOUNDATIONS) == FrameworkRole.DOMINANT
assert get_framework_role("reciprocal_teaching_think_aloud", LearnerStage.GUIDED_CONTROL) == FrameworkRole.DOMINANT
assert get_framework_role("gradual_release_of_responsibility", LearnerStage.INDEPENDENT_CONTROL) == FrameworkRole.DOMINANT
# Listening
assert get_framework_role("micro_listening_dictation", LearnerStage.FOUNDATIONS) == FrameworkRole.DOMINANT
assert get_framework_role("metacognitive_cycle", LearnerStage.GUIDED_CONTROL) == FrameworkRole.DOMINANT
assert get_framework_role("micro_listening_dictation", LearnerStage.AUTOMATIZATION) == FrameworkRole.RETIRED
# Speaking
assert get_framework_role("fluency_432", LearnerStage.FOUNDATIONS) == FrameworkRole.DOMINANT
assert get_framework_role("reformulation", LearnerStage.INDEPENDENT_CONTROL) == FrameworkRole.DOMINANT
assert get_framework_role("reformulation", LearnerStage.FOUNDATIONS) == FrameworkRole.FADED
print("✅ Framework roles match the spec tables\n")

print("=== Test 4: Shared spine has exactly 4 habits ===")
spine = get_shared_spine()
assert len(spine) == 4
spine_ids = {s["id"] for s in spine}
assert spine_ids == {
    "backward_design", "feedback_triad",
    "dynamic_assessment", "elicitation_before_telling"
}
print("✅ Shared spine complete\n")

print("=== Test 5: Support level fade/restore ===")
assert reduce_support(SupportLevel.FULL) == SupportLevel.PARTIAL
assert reduce_support(SupportLevel.NONE) == SupportLevel.NONE
assert restore_support(SupportLevel.NONE) == SupportLevel.MINIMAL
assert restore_support(SupportLevel.FULL) == SupportLevel.FULL
assert DEFAULT_SUPPORT_BY_STAGE[LearnerStage.FOUNDATIONS] == SupportLevel.FULL
assert DEFAULT_SUPPORT_BY_STAGE[LearnerStage.AUTOMATIZATION] == SupportLevel.NONE
print("✅ Support fade/restore correct\n")

print("=== Test 6: Band descriptors for all sections/criteria ===")
for section, expected in [
    ("Writing", 4), ("Reading", 4), ("Listening", 4), ("Speaking", 4)
]:
    cids = get_criterion_ids(section)
    assert len(cids) == expected, f"{section}: {cids}"
    for cid in cids:
        for band in [4.0, 5.5, 6.0, 7.0, 8.5, None]:
            text = get_descriptor(section, cid, band)
            assert text, f"Missing descriptor {section}/{cid}/{band}"
print("✅ Descriptors present for every criterion at every band\n")

print("=== Test 7: Target descriptor (Backward Design) ===")
target_band, text = get_target_descriptor("Writing", "grammatical_range_accuracy", 6.0)
assert target_band == 7.0
assert "error-free" in text or "complex" in text
target_band, text = get_target_descriptor("Writing", "task_response", None)
assert target_band == 5.0  # cold start targets band 5
target_band, _ = get_target_descriptor("Writing", "task_response", 8.5)
assert target_band == 9.0
print("✅ Target descriptors correct\n")

print("ALL REGISTRY TESTS PASSED")
