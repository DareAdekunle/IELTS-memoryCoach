import sys
sys.path.append('.')

from app.services.skill_classifier_service import classify_writing_skills
from app.services.skill_taxonomy_service import get_all_skill_ids

PROMPT = (
    "Some people believe that universities should focus only on "
    "academic studies, while others think universities should also "
    "prepare students for employment. Discuss both views and give "
    "your own opinion."
)

# A deliberately weak essay - vague thesis, no real conclusion,
# repetitive vocabulary, simple sentences only
WEAK_ESSAY = (
    "Universities are important. Some people think university is "
    "only for study. Other people think university should help you "
    "get a job. I think both things are important things. "
    "First, study is important because you learn many things at "
    "university. You learn about your subject and you become smart. "
    "This is good for you and good for the country also. "
    "Second, job skills are also important. If you cannot get a job "
    "after university then it is bad. Many students want a good job "
    "so universities should teach job skills too. This is also good "
    "for students because they need money to live. "
    "In conclusion, university is good for many reasons."
)

print("Classifying a deliberately weak essay...")
print("(This calls Qwen so may take 10-20 seconds)\n")

result = classify_writing_skills(PROMPT, WEAK_ESSAY)

expected_ids = set(get_all_skill_ids("Writing"))

print("=== Classification Result ===")
for skill_id, classification in result.items():
    print(f"  {skill_id:30} -> {classification}")

print()
print("=== Validation ===")
assert set(result.keys()) == expected_ids, "Missing or extra skill_ids!"
print(f"✅ All {len(expected_ids)} skill_ids present, no extras")

valid_values = {"demonstrated_strength", "demonstrated_weakness", "not_applicable"}
assert all(v in valid_values for v in result.values()), "Invalid classification value!"
print("✅ All classification values are valid")

weakness_count = sum(1 for v in result.values() if v == "demonstrated_weakness")
strength_count = sum(1 for v in result.values() if v == "demonstrated_strength")
na_count = sum(1 for v in result.values() if v == "not_applicable")

print(f"\nWeaknesses: {weakness_count} | Strengths: {strength_count} | N/A: {na_count}")
print("\n🎉 Skill classifier test passed!")
