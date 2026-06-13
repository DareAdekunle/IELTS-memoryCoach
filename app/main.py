import streamlit as st

st.set_page_config(
    page_title="IELTS MemoryCoach",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 IELTS MemoryCoach")
st.markdown("---")

st.markdown("""
### Welcome to your personal IELTS coach.

This app helps you prepare for IELTS by:
- 📝 Giving you real practice prompts
- 🤖 Scoring your answers with AI feedback
- 🧠 Remembering your weaknesses across sessions
- 📈 Tracking your improvement over time

---

### How to get started

👈 Use the **sidebar** to navigate between sections:

| Page | What it does |
|---|---|
| 🙋 Profile | Create your learner profile and set your target score |
| ✍️ Writing Coach | Practice IELTS writing and get AI feedback |
| 📈 Progress Dashboard | See how your scores are improving |
| 🧠 Memory Dashboard | See what your coach remembers about you |

---
""")

st.info("👈 Start by clicking **Profile** in the sidebar to create your learner profile.")