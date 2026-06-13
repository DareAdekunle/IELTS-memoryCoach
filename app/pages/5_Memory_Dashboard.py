import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.memory_service import get_all_memories, get_memory_stats

st.set_page_config(
    page_title="Memory Dashboard",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Memory Dashboard")
st.markdown("Everything your coach has learned about you across all sessions.")
st.markdown("---")

# Check for profile
if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning("👈 Please create your **Learner Profile** first.")
    st.stop()

learner_id = st.session_state["learner_id"]
learner_name = st.session_state.get("learner_name", "Learner")

# Load all memories and stats
all_memories = get_all_memories(learner_id)
stats = get_memory_stats(learner_id)

active_memories = all_memories["active"]
archived_memories = all_memories["archived"]

# ─── No memories yet ──────────────────────────────────────────────────────────
if stats["total_memories"] == 0:
    st.info(
        "🧠 No memories yet. Submit your first essay on the "
        "**Writing Coach** page and your coach will start building "
        "your memory profile."
    )
    st.stop()

# ─── Memory stats summary ─────────────────────────────────────────────────────
st.subheader(f"🧠 {learner_name}'s Memory Profile")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Memories", stats["total_memories"])
with col2:
    st.metric("Active Memories", stats["active_count"])
with col3:
    st.metric("Archived (Mastered)", stats["archived_count"])
with col4:
    avg_conf = int(stats["avg_confidence"] * 100)
    st.metric("Avg Confidence", f"{avg_conf}%")

st.markdown("---")

# ─── Active memories ──────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("🟢 Active Memories")
    st.caption("What your coach currently believes about you")

    if not active_memories:
        st.info("No active memories yet.")
    else:
        weaknesses = [m for m in active_memories if m["memory_type"] == "weakness"]
        strengths = [m for m in active_memories if m["memory_type"] == "strength"]
        preferences = [m for m in active_memories if m["memory_type"] == "preference"]

        if weaknesses:
            st.markdown("**⚠️ Areas to Work On**")
            for mem in weaknesses:
                confidence_pct = int(mem["confidence"] * 100)
                evidence = mem["evidence_count"]

                with st.container():
                    st.markdown(
                        f"**{mem['skill']}**  \n"
                        f"{mem['memory_text']}"
                    )

                    # Confidence bar
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.progress(mem["confidence"])
                    with col_b:
                        st.caption(f"{confidence_pct}%")

                    st.caption(
                        f"Section: {mem['section']} · "
                        f"Seen across {evidence} attempt(s)"
                    )
                    st.markdown("---")

        if strengths:
            st.markdown("**✅ Observed Strengths**")
            for mem in strengths:
                confidence_pct = int(mem["confidence"] * 100)

                with st.container():
                    st.markdown(
                        f"**{mem['skill']}**  \n"
                        f"{mem['memory_text']}"
                    )

                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.progress(mem["confidence"])
                    with col_b:
                        st.caption(f"{confidence_pct}%")

                    st.caption(f"Section: {mem['section']}")
                    st.markdown("---")

        if preferences:
            st.markdown("**💡 Learning Preferences**")
            for mem in preferences:
                st.markdown(
                    f"**{mem['skill']}**  \n"
                    f"{mem['memory_text']}"
                )
                st.markdown("---")

# ─── Archived memories ────────────────────────────────────────────────────────
with col2:
    st.subheader("📦 Archived Memories")
    st.caption("Skills your coach considers mastered")

    if not archived_memories:
        st.info(
            "No archived memories yet. Keep practising — "
            "when your coach sees consistent improvement in a skill, "
            "it will be archived here as mastered."
        )
    else:
        for mem in archived_memories:
            with st.container():
                icon = "✅" if mem["memory_type"] == "strength" else "🏆"
                st.markdown(
                    f"{icon} **{mem['skill']}**  \n"
                    f"~~{mem['memory_text']}~~"
                )
                st.caption(
                    f"Section: {mem['section']} · "
                    f"Mastered after {mem['evidence_count']} attempt(s)"
                )
                st.markdown("---")

st.markdown("---")

# ─── Recommended next focus ───────────────────────────────────────────────────
st.subheader("🎯 Recommended Next Focus")

if active_memories:
    # Find the weakness with highest confidence — most persistent problem
    weaknesses = [m for m in active_memories if m["memory_type"] == "weakness"]

    if weaknesses:
        top_weakness = max(weaknesses, key=lambda m: m["confidence"])
        confidence_pct = int(top_weakness["confidence"] * 100)
        evidence = top_weakness["evidence_count"]

        st.warning(
            f"Your coach most strongly recommends focusing on "
            f"**{top_weakness['skill']}**.  \n\n"
            f"{top_weakness['memory_text']}  \n\n"
            f"This has been observed across **{evidence} attempt(s)** "
            f"with **{confidence_pct}% confidence**."
        )
    else:
        st.success(
            "✅ Your coach has not identified any persistent weaknesses. "
            "Keep up the great work!"
        )
else:
    st.info("Submit more essays to get a personalised recommendation.")
