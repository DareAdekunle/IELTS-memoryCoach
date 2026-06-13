import streamlit as st

st.set_page_config(
    page_title="Memory Dashboard",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Memory Dashboard")
st.markdown("See everything your coach has learned about you across sessions.")
st.markdown("---")

if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning("👈 Please create your **Learner Profile** first.")
    st.stop()

# Placeholder content — Phase 10 will replace with real memory data
col1, col2 = st.columns(2)

with col1:
    st.subheader("🟢 Active Memories")
    st.info("Your coach's active observations about your skills will appear here.")

with col2:
    st.subheader("📦 Archived Memories")
    st.info("Skills you have mastered will be archived here.")

st.markdown("---")
st.subheader("🎯 Recommended Next Focus")
st.info("Your personalised next focus area will appear here after your first attempt.")