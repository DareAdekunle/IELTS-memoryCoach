import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.chat_coach_service import (
    start_chat_session,
    continue_chat_session
)

st.set_page_config(
    page_title="Chat Coach",
    page_icon="💬",
    layout="wide"
)

st.title("💬 Chat Coach")
st.markdown(
    "A personal conversation with your coach about your IELTS writing."
)
st.markdown("---")

# ─── Profile check ────────────────────────────────────────────────────────────
if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning(
        "👈 Please create your **Learner Profile** first "
        "before chatting with your coach."
    )
    st.stop()

learner_id = st.session_state["learner_id"]

# ─── Session state defaults ───────────────────────────────────────────────────
# chat_messages holds the FULL conversation for display: every
# message, both roles, in order. This is what st.chat_message
# renders directly. It is intentionally session-only -- nothing
# here is written to the database (locked design decision).
defaults = {
    "chat_messages": [],          # [{"role": "assistant"/"user", "content": "..."}]
    "chat_system_prompt": None,    # the system prompt built for this session
    "chat_state": None,            # current state: introduction/explaining/drilling/bridge_to_practice
    "chat_started": False,
    "chat_has_history": None,
    "chat_learner_id": None,       # which learner_id this session was built for
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_chat():
    """Clears the current chat session, starting fresh on next load."""
    for key, val in defaults.items():
        st.session_state[key] = val

# ─── Detect a profile switch and force a fresh session ────────────────────────
# st.session_state survives across profile switches within the same browser
# session, but a conversation built for Learner A should never be shown to
# Learner B. If the active learner_id doesn't match who this chat session
# was built for, reset before doing anything else.
if (st.session_state["chat_started"]
        and st.session_state["chat_learner_id"] != learner_id):
    reset_chat()

# ─── Start a new session if one hasn't started yet ────────────────────────────
if not st.session_state["chat_started"]:
    with st.spinner("Your coach is reviewing your progress..."):
        result = start_chat_session(learner_id, section="Writing")

    st.session_state["chat_messages"] = [
        {"role": "assistant", "content": result["message"]}
    ]
    st.session_state["chat_state"] = result["state"]
    st.session_state["chat_has_history"] = result["has_history"]
    st.session_state["chat_system_prompt"] = result.get("system_prompt")
    st.session_state["chat_started"] = True
    st.session_state["chat_learner_id"] = learner_id

# ─── State banner ──────────────────────────────────────────────────────────────
# A small, honest indicator of where we are in the session -- purely
# informational, never blocks anything.
state_labels = {
    "introduction": "🟢 Getting started",
    "explaining": "📘 Learning the skill",
    "drilling": "✏️ Practising with drills",
    "bridge_to_practice": "🎯 Ready for a full essay"
}
current_state = st.session_state["chat_state"]

if st.session_state["chat_has_history"]:
    label = state_labels.get(current_state, "")
    if label:
        st.caption(label)

# ─── Conversation display ──────────────────────────────────────────────────────
for msg in st.session_state["chat_messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─── Bridge to practice ─────────────────────────────────────────────────────────
# Shown only when the coach has explicitly signalled readiness via
# the state tag -- this is the deterministic check Option B was
# built for. Placed before the input box so it's visible without
# scrolling once reached.
if current_state == "bridge_to_practice":
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(
            "🎯 Your coach thinks you're ready to put this into "
            "practice in a full essay!"
        )
    with col2:
        if st.button("Go to Writing Coach →", use_container_width=True):
            st.switch_page("pages/2_Writing_Coach.py")

# ─── Chat input ─────────────────────────────────────────────────────────────────
st.markdown("---")
learner_input = st.chat_input("Type your message...")

if learner_input:
    # Display the learner's message immediately
    st.session_state["chat_messages"].append(
        {"role": "user", "content": learner_input}
    )

    if not st.session_state["chat_has_history"]:
        # New learner with no history -- just nudge them toward
        # Writing Coach again rather than running the full state
        # machine, since there's no skill context to teach yet
        st.session_state["chat_messages"].append({
            "role": "assistant",
            "content": (
                "I'll be able to help much more once you've tried "
                "the Writing Coach! Head over there to submit your "
                "first essay, then come back and chat with me 😊"
            )
        })
        st.rerun()

    with st.spinner("Your coach is thinking..."):
        # Build the history to send -- everything EXCEPT the message
        # we just appended, since continue_chat_session appends it
        # itself
        history_for_call = st.session_state["chat_messages"][:-1]

        result = continue_chat_session(
            system_prompt=st.session_state["chat_system_prompt"],
            conversation_history=history_for_call,
            learner_message=learner_input
        )

    st.session_state["chat_messages"].append(
        {"role": "assistant", "content": result["message"]}
    )
    st.session_state["chat_state"] = result["state"]

    st.rerun()

# ─── Reset option ───────────────────────────────────────────────────────────────
st.markdown("---")
if st.button("🔄 Start a New Conversation"):
    reset_chat()
    st.rerun()

