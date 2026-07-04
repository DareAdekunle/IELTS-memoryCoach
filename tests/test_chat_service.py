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
    system_prompt = result["system_prompt"]

    # Build conversation history manually, simulating a back-and-forth
    history = [
        {"role": "assistant", "content": result["message"]}
    ]

    print("=" * 60)
    print("=== Learner responds: 'Yes I'm ready, let's work on it' ===\n")

    turn2 = continue_chat_session(
        system_prompt=system_prompt,
        conversation_history=history,
        learner_message="Yes I'm ready, let's work on it"
    )
    print(f"state: {turn2['state']}")
    print(f"\nCoach says:\n{turn2['message']}\n")

    history.append({"role": "user", "content": "Yes I'm ready, let's work on it"})
    history.append({"role": "assistant", "content": turn2["message"]})

    print("=" * 60)
    print("=== Learner asks an off-topic question ===\n")

    turn3 = continue_chat_session(
        system_prompt=system_prompt,
        conversation_history=history,
        learner_message="What's the weather like today?"
    )
    print(f"state: {turn3['state']}")
    print(f"\nCoach says:\n{turn3['message']}\n")

print("\n🎉 Chat service test complete!")

