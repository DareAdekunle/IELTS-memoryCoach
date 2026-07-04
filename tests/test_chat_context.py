import sys
sys.path.append('.')

from app.services.memory_service import build_chat_coach_context

# Use a learner_id you've actually been testing with -- one that has
# real essay history. Replace this with your real learner_id.
# You can find it in DB Browser -> learners table -> learner_id column.
LEARNER_ID = "61b81d9b"

print("=== Test 1: Returning learner with history ===")
context = build_chat_coach_context(LEARNER_ID, section="Writing")

print(f"has_history: {context['has_history']}")

if context["has_history"]:
    weakest = context["weakest_skill"]
    print(f"\nWeakest skill: {weakest['skill_id']}")
    print(f"  Skill name: {context['skill_definition']['skill_name']}")
    print(f"  Current rank: {weakest['current_rank']} "
          f"({weakest['rank_name']})")
    print(f"  Clean streak: {weakest['clean_streak']}")
    print(f"  Total evidence: {weakest['total_evidence']}")

    print(f"\nCurrent rank definition:")
    print(f"  {context['current_rank_text']}")
    print(f"\nNext rank definition (what to aim for):")
    print(f"  {context['next_rank_text']}")

    if context["evidence_memory"]:
        print(f"\nEvidence memory found:")
        print(f"  Type: {context['evidence_memory']['memory_type']}")
        print(f"  Text: {context['evidence_memory']['memory_text']}")
    else:
        print("\nNo specific evidence memory found (will rely on rank "
              "definitions alone)")

    if context["recent_essay"]:
        print(f"\nMost recent essay found:")
        print(f"  Prompt: {context['recent_essay']['prompt'][:80]}...")
        print(f"  Essay length: {len(context['recent_essay']['essay'])} chars")
    else:
        print("\nNo recent essay found")

print("\n" + "="*60)
print("=== Test 2: Brand new learner with zero history ===")
fake_new_learner = "definitely_does_not_exist_999"
context2 = build_chat_coach_context(fake_new_learner, section="Writing")
print(f"has_history: {context2['has_history']}")
assert context2["has_history"] is False, (
    "A learner with no data at all should have has_history=False"
)
print("✅ New learner correctly falls back to no-history state")

print("\n🎉 Context builder test complete!")
