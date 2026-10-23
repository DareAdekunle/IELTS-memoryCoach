import sys
sys.path.append('.')

from app.services.memory_service import (
    apply_skill_classification,
    apply_skill_classifications_batch,
    get_skill_rank,
    get_weakest_skill,
    get_skill_progress_summary
)
from app.services.skill_taxonomy_service import (
    get_all_skill_ids,
    format_skill_list_for_prompt,
    get_rank_definition
)

TEST_LEARNER = "test_learner_skill_rank"
SECTION = "Writing"

print("=== Test 1: Taxonomy loads correctly ===")
skill_ids = get_all_skill_ids(SECTION)
print(f"Found {len(skill_ids)} skills")
assert len(skill_ids) == 13, "Expected 13 skills"
print("✅ Taxonomy loads with 13 skills\n")

print("=== Test 2: Prompt formatting works ===")
formatted = format_skill_list_for_prompt(SECTION)
print(formatted[:300] + "...\n")
print("✅ Prompt formatting works\n")

print("=== Test 3: Fresh skill starts at rank 1, no evidence ===")
rank = get_skill_rank(TEST_LEARNER, SECTION, "tr_conclusion_synthesis")
print(rank)
assert rank["current_rank"] == 1
assert rank["exists"] is False
print("✅ Fresh skill correctly defaults to rank 1\n")

print("=== Test 4: not_applicable does nothing ===")
result = apply_skill_classification(
    TEST_LEARNER, SECTION, "tr_conclusion_synthesis", "not_applicable"
)
print(result)
assert result["changed"] is False
rank = get_skill_rank(TEST_LEARNER, SECTION, "tr_conclusion_synthesis")
assert rank["exists"] is False, "not_applicable should not create a row"
print("✅ not_applicable correctly ignored\n")

print("=== Test 5: 3 consecutive strengths triggers rank-up ===")
for i in range(1, 4):
    result = apply_skill_classification(
        TEST_LEARNER, SECTION, "tr_conclusion_synthesis", "demonstrated_strength"
    )
    print(f"  Attempt {i}: streak={result['clean_streak']}, "
          f"rank={result['current_rank']}, ranked_up={result['ranked_up']}")

assert result["current_rank"] == 2, f"Expected rank 2, got {result['current_rank']}"
assert result["ranked_up"] is True
assert result["clean_streak"] == 0, "Streak should reset after rank-up"
print("✅ Rank correctly moved from 1 to 2 after 3 clean attempts\n")

print("=== Test 6: A weakness resets the streak fully ===")
apply_skill_classification(
    TEST_LEARNER, SECTION, "tr_conclusion_synthesis", "demonstrated_strength"
)
apply_skill_classification(
    TEST_LEARNER, SECTION, "tr_conclusion_synthesis", "demonstrated_strength"
)
rank = get_skill_rank(TEST_LEARNER, SECTION, "tr_conclusion_synthesis")
print(f"  Before weakness: streak={rank['clean_streak']}, rank={rank['current_rank']}")
assert rank["clean_streak"] == 2

result = apply_skill_classification(
    TEST_LEARNER, SECTION, "tr_conclusion_synthesis", "demonstrated_weakness"
)
print(f"  After weakness: streak={result['clean_streak']}, rank={result['current_rank']}")
assert result["clean_streak"] == 0
assert result["current_rank"] == 2, "Rank should NOT decrease"
print("✅ Weakness resets streak to 0 without lowering rank\n")

print("=== Test 7: Rank is capped at 5 ===")
# Push tr_conclusion_synthesis from rank 2 all the way to rank 5
for _ in range(20):
    result = apply_skill_classification(
        TEST_LEARNER, SECTION, "tr_conclusion_synthesis", "demonstrated_strength"
    )
print(f"  Final rank: {result['current_rank']}")
assert result["current_rank"] == 5, "Rank should be capped at 5"
assert result["ranked_up"] is False, "Should not rank up further once at cap"
print("✅ Rank correctly capped at 5\n")

print("=== Test 8: Batch classification across multiple skills ===")
batch_result = apply_skill_classifications_batch(
    TEST_LEARNER, SECTION,
    {
        "tr_full_coverage": "demonstrated_weakness",
        "cc_paragraphing": "demonstrated_strength",
        "lr_range": "not_applicable",
        "gra_punctuation": "demonstrated_strength"
    }
)
for r in batch_result:
    print(f"  {r['skill_id']}: changed={r['changed']}")
assert len(batch_result) == 4
print("✅ Batch classification works across multiple skills\n")

print("=== Test 9: Weakest skill detection ===")
weakest = get_weakest_skill(TEST_LEARNER, SECTION)
print(f"  Weakest skill: {weakest['skill_id']} "
      f"(rank {weakest['current_rank']}, {weakest['rank_name']})")
# tr_full_coverage was just marked weakness and is still rank 1 -- should
# be tied with many untouched skills at rank 1, but it has evidence + a
# recent weakness so it should win the tiebreak over untouched skills
assert weakest["current_rank"] == 1
print("✅ Weakest skill correctly identified\n")

print("=== Test 10: Progress summary ===")
summary = get_skill_progress_summary(TEST_LEARNER, SECTION)
print(summary)
assert summary["total_skills"] == 13
assert summary["skills_at_max"] >= 1  # tr_conclusion_synthesis hit rank 5
print("✅ Progress summary works\n")

print("=== Test 11: Rank definition lookup ===")
definition = get_rank_definition("tr_conclusion_synthesis", 3, SECTION)
print(f"  Rank 3 definition: {definition}")
assert len(definition) > 0
print("✅ Rank definition lookup works\n")

print("🎉 ALL SKILL RANKING TESTS PASSED")
