import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.memory_service import get_progress_data, get_memory_stats

st.set_page_config(
    page_title="Progress Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Progress Dashboard")
st.markdown("Track how your IELTS skills are improving over time.")
st.markdown("---")

# Check for profile
if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning("👈 Please create your **Learner Profile** first.")
    st.stop()

learner_id = st.session_state["learner_id"]
learner_name = st.session_state.get("learner_name", "Learner")

# Load progress data
data = get_progress_data(learner_id, section="Writing")
memory_stats = get_memory_stats(learner_id)

# ─── No attempts yet ──────────────────────────────────────────────────────────
if data["total_attempts"] == 0:
    st.info(
        "📝 No attempts yet. Go to the **Writing Coach** page to submit "
        "your first essay and your progress will appear here."
    )
    st.stop()

# ─── Summary metrics ──────────────────────────────────────────────────────────
st.subheader(f"📊 {learner_name}'s Writing Progress")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Total Attempts",
        value=data["total_attempts"]
    )

with col2:
    st.metric(
        label="Active Memories",
        value=memory_stats["active_count"]
    )

with col3:
    st.metric(
        label="Skills Mastered",
        value=memory_stats["archived_count"]
    )

with col4:
    avg_confidence = memory_stats.get("avg_confidence", 0)
    st.metric(
        label="Avg Memory Confidence",
        value=f"{int(avg_confidence * 100)}%"
    )

st.markdown("---")

# ─── Latest skill scores ──────────────────────────────────────────────────────
st.subheader("🎯 Latest Skill Scores")

skill_labels = {
    "thesis_clarity": "Thesis Clarity",
    "organization": "Organization",
    "grammar": "Grammar",
    "vocabulary": "Vocabulary",
    "idea_development": "Idea Development"
}

latest = data["latest_scores"]
averages = data.get("skill_averages", {})

cols = st.columns(5)
for i, (skill_key, label) in enumerate(skill_labels.items()):
    with cols[i]:
        latest_score = latest.get(skill_key, 0)
        avg_score = averages.get(skill_key, 0)

        # Calculate delta from average to show trend
        delta = round(latest_score - avg_score, 1)
        delta_str = f"{delta:+.1f} vs avg" if data["total_attempts"] > 1 else None

        st.metric(
            label=label,
            value=f"{latest_score} / 5",
            delta=delta_str
        )

st.markdown("---")

# ─── Score trend chart ────────────────────────────────────────────────────────
if data["total_attempts"] > 1:
    st.subheader("📉 Score Trends Over Time")
    st.caption("How each skill has changed across your attempts")

    # Build chart data
    # Streamlit's line_chart needs a dict of lists
    chart_data = {}
    for skill_key, label in skill_labels.items():
        trend = data["skill_trends"].get(skill_key, [])
        if trend:
            chart_data[label] = trend

    if chart_data:
        st.line_chart(chart_data)

    st.markdown("---")

# ─── Skill breakdown table ────────────────────────────────────────────────────
st.subheader("📋 Skill Breakdown")

best_skill = data.get("best_skill")
worst_skill = data.get("worst_skill")

rows = []
for skill_key, label in skill_labels.items():
    avg = averages.get(skill_key, 0)
    trend = data["skill_trends"].get(skill_key, [])
    latest_val = trend[-1] if trend else 0
    first_val = trend[0] if trend else 0

    if len(trend) > 1:
        change = latest_val - first_val
        if change > 0:
            trend_icon = "📈 Improving"
        elif change < 0:
            trend_icon = "📉 Declining"
        else:
            trend_icon = "➡️ Stable"
    else:
        trend_icon = "⬜ First attempt"

    tag = ""
    if skill_key == best_skill:
        tag = " 🏆"
    elif skill_key == worst_skill:
        tag = " ⚠️"

    rows.append({
        "Skill": label + tag,
        "Average Score": f"{avg} / 5",
        "Latest Score": f"{latest_val} / 5",
        "Trend": trend_icon
    })

st.table(rows)

st.markdown("---")

# ─── Recommended next focus ───────────────────────────────────────────────────
st.subheader("🎯 Recommended Next Focus")

if worst_skill:
    worst_label = skill_labels.get(worst_skill, worst_skill)
    worst_avg = averages.get(worst_skill, 0)

    st.warning(
        f"Based on your attempts so far, your coach recommends focusing on "
        f"**{worst_label}** next. Your average score in this area is "
        f"**{worst_avg} / 5** — the lowest across all your skills."
    )
else:
    st.info("Complete more attempts to get a personalised recommendation.")

# ─── Attempt history ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📜 Attempt History")

attempts = data["attempts"]
for attempt in reversed(attempts):
    with st.expander(
        f"Attempt {attempt['attempt_number']} — "
        f"{attempt['created_at'][:16].replace('T', ' at ')}"
    ):
        scores = attempt["scores"]
        cols = st.columns(5)
        for i, (skill_key, label) in enumerate(skill_labels.items()):
            with cols[i]:
                st.metric(label, f"{scores.get(skill_key, 0)} / 5")

        if attempt["feedback"]:
            st.markdown(f"**Coach feedback:** {attempt['feedback']}")
