"""Manual check against the LIVE Qwen API (costs credit). Not run by pytest.
Run from repo root: python scripts/manual_checks/chat_service_live.py
"""
import sys
sys.path.append('.')

from app.services.chat_coach_service import (
    start_chat_session,
    continue_chat_session
)

# Use the SAME real learner_id you used in Phase 1 testing --
# one with actual Writing essay history
LEARNER_ID = "61b81d9b"

print("=== Starting chat session ===\n")
result = start_chat_session(LEARNER_ID, section="Writing")

print(f"has_history: {result['has_history']}")
print(f"state: {result['state']}")
print(f"\nCoach says:\n{result['message']}\n")

assert result["state"] in (
    "introduction", "explaining", "drilling", "bridge_to_practice"
), "State should always be a valid value"
print("✅ Valid state returned\n")

if not result["has_history"]:
    print("This learner has no history -- stopping test here.")
    print("(Re-run with a learner_id that has essay history to test "
          "the full conversation flow.)")
else:
    # The prompt and transcript are held server-side; only session_id travels.
    session_id = result["session_id"]

    print("=" * 60)
    print("=== Learner responds: 'Yes I'm ready, let's work on it' ===\n")
    turn2 = continue_chat_session(session_id, LEARNER_ID, "Yes I'm ready, let's work on it")
    print(f"state: {turn2['state']}")
    print(f"\nCoach says:\n{turn2['message']}\n")

    print("=" * 60)
    print("=== Learner asks an off-topic question ===\n")
    turn3 = continue_chat_session(session_id, LEARNER_ID, "What's the weather like today?")
    print(f"state: {turn3['state']}")
    print(f"\nCoach says:\n{turn3['message']}\n")

print("\n🎉 Chat service test complete!")

