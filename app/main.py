import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(
    page_title="IELTS MemoryCoach",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 IELTS MemoryCoach")
st.markdown("*Your personal AI-powered IELTS coach with persistent memory*")
st.markdown("---")

# Show current session status
if "learner_id" in st.session_state and st.session_state["learner_id"]:
    learner_name = st.session_state.get("learner_name", "Learner")
    st.success(f"👋 Welcome back, **{learner_name}**! Your coach remembers you.")
else:
    st.info("👈 Get started by clicking **Profile** in the sidebar.")

st.markdown("---")

# App overview
col1, col2 = st.columns(2)

with col1:
    st.markdown("### What this app does")
    st.markdown("""
    IELTS MemoryCoach is not just an essay grader.
    It is a coaching system that **remembers you** across sessions.

    Every time you practise:
    - 📝 You get a real IELTS writing prompt
    - 🤖 Your essay is scored by AI against an official rubric
    - 🧠 Your coach extracts memories from your performance
    - 📈 Those memories get stronger or weaker over time
    - 🎯 Feedback becomes more personalised with every attempt
    """)

with col2:
    st.markdown("### How the memory works")
    st.markdown("""
    The MemoryAgent tracks your patterns over time:

    | What happens | What the coach does |
    |---|---|
    | You write a weak thesis | Coach notes this as a weakness |
    | Same weakness appears again | Confidence in memory increases |
    | You start improving | Memory confidence decreases |
    | You master the skill | Memory gets archived |

    This means your coach gets smarter about **you** specifically —
    not just IELTS in general.
    """)

st.markdown("---")

# Navigation guide
st.markdown("### Where to go")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("#### 🙋 Profile")
    st.markdown("Create your learner profile and set your target band score.")

with col2:
    st.markdown("#### ✍️ Writing Coach")
    st.markdown("Submit IELTS essays and receive personalised AI feedback.")

with col3:
    st.markdown("#### 📈 Progress")
    st.markdown("See your score trends and which skills are improving.")

with col4:
    st.markdown("#### 🧠 Memory")
    st.markdown("See everything your coach has learned about you.")

st.markdown("---")
st.caption(
    "Built with Streamlit · Powered by Qwen AI · "
    "Memory stored in SQLite · Containerised with Docker"
)