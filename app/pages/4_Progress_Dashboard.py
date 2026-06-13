import streamlit as st

st.set_page_config(
    page_title="Progress Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Progress Dashboard")
st.markdown("Track how your IELTS skills are improving over time.")
st.markdown("---")

if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning("👈 Please create your **Learner Profile** first.")
    st.stop()

# Placeholder content — Phase 10 will replace this with real data
st.subheader("Your IELTS Progress")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Writing", value="--", delta=None)
with col2:
    st.metric(label="Reading", value="--", delta=None)
with col3:
    st.metric(label="Speaking", value="--", delta=None)
with col4:
    st.metric(label="Listening", value="--", delta=None)

st.markdown("---")
st.info("📊 Your progress charts will appear here after your first practice attempt.")