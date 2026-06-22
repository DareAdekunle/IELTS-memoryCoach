import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.memory_service import (
    get_progress_data,
    get_memory_stats,
    get_speaking_progress_data,
    get_listening_progress_data
)

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

# Load data for both sections
writing_data = get_progress_data(learner_id, section="Writing")
reading_data = get_progress_data(learner_id, section="Reading")
memory_stats = get_memory_stats(learner_id)

# ─── Top level summary ────────────────────────────────────────────────────────
st.subheader(f"📊 {learner_name}'s IELTS Overview")

speaking_data_summary = get_speaking_progress_data(learner_id)
listening_data_summary = get_listening_progress_data(learner_id)

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("Writing Attempts", writing_data["total_attempts"])
with col2:
    st.metric("Reading Attempts", reading_data["total_attempts"])
with col3:
    st.metric(
        "Speaking Attempts",
        speaking_data_summary["total_attempts"]
    )
with col4:
    st.metric(
        "Listening Attempts",
        listening_data_summary["total_attempts"]
    )
with col5:
    st.metric("Active Memories", memory_stats["active_count"])
with col6:
    st.metric("Skills Mastered", memory_stats["archived_count"])

st.markdown("---")

# ─── Section tabs ─────────────────────────────────────────────────────────────
writing_tab, reading_tab, speaking_tab, listening_tab = st.tabs([
    "✍️ Writing Progress",
    "📖 Reading Progress",
    "🎤 Speaking Progress",
    "🎧 Listening Progress"
])


# ══════════════════════════════════════════════════════════════════════════════
# WRITING TAB
# ══════════════════════════════════════════════════════════════════════════════
with writing_tab:

    if writing_data["total_attempts"] == 0:
        st.info(
            "📝 No writing attempts yet. Go to the **Writing Coach** page "
            "to submit your first essay."
        )
    else:
        data = writing_data

        skill_labels = {
            "thesis_clarity": "Thesis Clarity",
            "organization": "Organization",
            "grammar": "Grammar",
            "vocabulary": "Vocabulary",
            "idea_development": "Idea Development"
        }

        # Latest skill scores
        st.subheader("🎯 Latest Writing Scores")
        latest = data["latest_scores"]
        averages = data.get("skill_averages", {})

        cols = st.columns(5)
        for i, (skill_key, label) in enumerate(skill_labels.items()):
            with cols[i]:
                latest_score = latest.get(skill_key, 0)
                avg_score = averages.get(skill_key, 0)
                delta = round(latest_score - avg_score, 1)
                delta_str = (
                    f"{delta:+.1f} vs avg"
                    if data["total_attempts"] > 1 else None
                )
                st.metric(
                    label=label,
                    value=f"{latest_score} / 5",
                    delta=delta_str
                )

        # Score trend chart
        if data["total_attempts"] > 1:
            st.markdown("---")
            st.subheader("📉 Writing Score Trends")
            st.caption("How each skill has changed across your attempts")

            chart_data = {}
            for skill_key, label in skill_labels.items():
                trend = data["skill_trends"].get(skill_key, [])
                if trend:
                    chart_data[label] = trend

            if chart_data:
                st.line_chart(chart_data)

        # Skill breakdown table
        st.markdown("---")
        st.subheader("📋 Writing Skill Breakdown")

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

        # Recommended focus
        st.markdown("---")
        st.subheader("🎯 Recommended Writing Focus")

        if worst_skill:
            worst_label = skill_labels.get(worst_skill, worst_skill)
            worst_avg = averages.get(worst_skill, 0)
            st.warning(
                f"Your coach recommends focusing on **{worst_label}**. "
                f"Your average score is **{worst_avg} / 5** — "
                f"the lowest across all writing skills."
            )

        # Attempt history
        st.markdown("---")
        st.subheader("📜 Writing Attempt History")

        for attempt in reversed(data["attempts"]):
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


# ══════════════════════════════════════════════════════════════════════════════
# READING TAB
# ══════════════════════════════════════════════════════════════════════════════
with reading_tab:

    if reading_data["total_attempts"] == 0:
        st.info(
            "📖 No reading attempts yet. Go to the **Reading Coach** page "
            "to complete your first passage."
        )
    else:
        data = reading_data

        # Reading skill labels
        reading_skill_labels = {
            "main_idea": "Main Idea",
            "detail_retrieval": "Detail Retrieval",
            "inference": "Inference",
            "vocabulary_in_context": "Vocabulary in Context",
            "true_false_ng": "True / False / NG"
        }

        # Latest scores
        st.subheader("🎯 Latest Reading Scores")
        latest = data["latest_scores"]
        averages = data.get("skill_averages", {})

        # Show latest attempt percentage score prominently
        latest_attempt = data["attempts"][-1]
        if latest_attempt.get("percentage") is not None:
            pct = latest_attempt["percentage"]
            total = latest_attempt.get("total_score", "?")
            maximum = latest_attempt.get("max_score", "?")

            if pct >= 80:
                st.success(
                    f"Latest attempt: **{total} / {maximum}** ({pct}%) 🎉"
                )
            elif pct >= 60:
                st.warning(
                    f"Latest attempt: **{total} / {maximum}** ({pct}%) 👍"
                )
            else:
                st.error(
                    f"Latest attempt: **{total} / {maximum}** ({pct}%) 📚"
                )

        # Skill scores converted to /5 scale
        if latest:
            skill_cols = st.columns(len(latest))
            for i, (skill_key, score) in enumerate(latest.items()):
                with skill_cols[i]:
                    label = reading_skill_labels.get(
                        skill_key,
                        skill_key.replace("_", " ").title()
                    )
                    st.metric(label=label, value=f"{score} / 5")

        # Score trend chart
        if data["total_attempts"] > 1:
            st.markdown("---")
            st.subheader("📉 Reading Score Trends")
            st.caption("Skill scores converted to /5 scale across attempts")

            chart_data = {}
            for skill_key, trend in data["skill_trends"].items():
                label = reading_skill_labels.get(
                    skill_key,
                    skill_key.replace("_", " ").title()
                )
                if trend:
                    chart_data[label] = trend

            if chart_data:
                st.line_chart(chart_data)

        # Skill breakdown table
        st.markdown("---")
        st.subheader("📋 Reading Skill Breakdown")

        best_skill = data.get("best_skill")
        worst_skill = data.get("worst_skill")

        rows = []
        for skill_key, avg in averages.items():
            label = reading_skill_labels.get(
                skill_key,
                skill_key.replace("_", " ").title()
            )
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

        if rows:
            st.table(rows)

        # Recommended reading focus
        st.markdown("---")
        st.subheader("🎯 Recommended Reading Focus")

        if worst_skill:
            worst_label = reading_skill_labels.get(
                worst_skill,
                worst_skill.replace("_", " ").title()
            )
            worst_avg = averages.get(worst_skill, 0)
            st.warning(
                f"Your coach recommends focusing on **{worst_label}** "
                f"in your reading practice. "
                f"Your average score is **{worst_avg} / 5**."
            )

        # Reading attempt history
        st.markdown("---")
        st.subheader("📜 Reading Attempt History")

        for attempt in reversed(data["attempts"]):
            title = attempt.get("passage_title") or "Reading Attempt"
            pct = attempt.get("percentage", "?")
            total = attempt.get("total_score", "?")
            maximum = attempt.get("max_score", "?")

            with st.expander(
                f"Attempt {attempt['attempt_number']} — {title} — "
                f"{total}/{maximum} ({pct}%) — "
                f"{attempt['created_at'][:16].replace('T', ' at ')}"
            ):
                scores = attempt["scores"]
                if scores:
                    cols = st.columns(len(scores))
                    for i, (skill_key, score) in enumerate(scores.items()):
                        label = reading_skill_labels.get(
                            skill_key,
                            skill_key.replace("_", " ").title()
                        )
                        with cols[i]:
                            st.metric(label, f"{score} / 5")

                if attempt["feedback"]:
                    st.markdown(f"**Result:** {attempt['feedback']}")


# ══════════════════════════════════════════════════════════════════════════════
# SPEAKING TAB
# ══════════════════════════════════════════════════════════════════════════════
with speaking_tab:

    speaking_data = get_speaking_progress_data(learner_id)

    if speaking_data["total_attempts"] == 0:
        st.info(
            "🎤 No speaking attempts yet. Go to the **Speaking Coach** "
            "page to complete your first speaking session."
        )
    else:
        criterion_labels = {
            "fluency_coherence": "Fluency & Coherence",
            "lexical_resource": "Lexical Resource",
            "grammatical_range": "Grammatical Range",
            "pronunciation_clarity": "Pronunciation"
        }

        # Latest attempt summary
        latest = speaking_data["latest_scores"]
        overall_band = latest.get("overall_band", 0)

        st.subheader("🎯 Latest Speaking Scores")

        if overall_band >= 7.0:
            st.success(
                f"Latest Overall Band: **{overall_band}** 🎉"
            )
        elif overall_band >= 5.5:
            st.warning(
                f"Latest Overall Band: **{overall_band}** 👍"
            )
        else:
            st.error(
                f"Latest Overall Band: **{overall_band}** 📚"
            )

        # Four criterion scores
        averages = speaking_data.get("criterion_averages", {})
        col1, col2, col3, col4 = st.columns(4)
        cols = [col1, col2, col3, col4]
        criteria = list(criterion_labels.keys())

        for i, criterion in enumerate(criteria):
            with cols[i]:
                score = latest.get(criterion, 0)
                avg = averages.get(criterion, 0)
                delta = round(score - avg, 1)
                delta_str = (
                    f"{delta:+.1f} vs avg"
                    if speaking_data["total_attempts"] > 1
                    else None
                )
                st.metric(
                    label=criterion_labels[criterion],
                    value=f"{score} / 9",
                    delta=delta_str
                )

        # Band score trend chart
        if speaking_data["total_attempts"] > 1:
            st.markdown("---")
            st.subheader("📉 Band Score Trends")
            st.caption(
                "How your band scores have changed across attempts"
            )

            chart_data = {}
            for criterion, label in criterion_labels.items():
                trend = speaking_data["band_trends"].get(criterion, [])
                if trend:
                    chart_data[label] = trend

            overall_trend = speaking_data["band_trends"].get(
                "overall_band", []
            )
            if overall_trend:
                chart_data["Overall Band"] = overall_trend

            if chart_data:
                st.line_chart(chart_data)

        # Criterion breakdown table
        st.markdown("---")
        st.subheader("📋 Criterion Breakdown")

        best = speaking_data.get("best_criterion")
        worst = speaking_data.get("worst_criterion")

        rows = []
        for criterion, label in criterion_labels.items():
            avg = averages.get(criterion, 0)
            trend = speaking_data["band_trends"].get(criterion, [])
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
            if criterion == best:
                tag = " 🏆"
            elif criterion == worst:
                tag = " ⚠️"

            rows.append({
                "Criterion": label + tag,
                "Average Score": f"{avg} / 9",
                "Latest Score": f"{latest_val} / 9",
                "Trend": trend_icon
            })

        st.table(rows)

        # Recommended focus
        st.markdown("---")
        st.subheader("🎯 Recommended Speaking Focus")

        if worst:
            worst_label = criterion_labels.get(worst, worst)
            worst_avg = averages.get(worst, 0)
            st.warning(
                f"Your coach recommends focusing on "
                f"**{worst_label}**. "
                f"Your average score is **{worst_avg} / 9** — "
                f"the lowest across all speaking criteria."
            )

        # Attempt history
        st.markdown("---")
        st.subheader("📜 Speaking Attempt History")

        for attempt in reversed(speaking_data["attempts"]):
            with st.expander(
                f"Attempt {attempt['attempt_number']} — "
                f"{attempt['topic']} — "
                f"Band {attempt['overall_band']} — "
                f"{attempt['created_at'][:16].replace('T', ' at ')}"
            ):
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric(
                        "Overall Band",
                        attempt["overall_band"]
                    )
                with col2:
                    st.metric(
                        "Fluency",
                        f"{attempt['fluency_coherence']}/9"
                    )
                with col3:
                    st.metric(
                        "Lexical",
                        f"{attempt['lexical_resource']}/9"
                    )
                with col4:
                    st.metric(
                        "Grammar",
                        f"{attempt['grammatical_range']}/9"
                    )
                with col5:
                    st.metric(
                        "Pronunciation",
                        f"{attempt['pronunciation_clarity']}/9"
                    )

                if attempt["feedback"]:
                    st.markdown(f"**Result:** {attempt['feedback']}")


# ══════════════════════════════════════════════════════════════════════════════
# LISTENING TAB
# ══════════════════════════════════════════════════════════════════════════════
with listening_tab:

    listening_data = get_listening_progress_data(learner_id)

    if listening_data["total_attempts"] == 0:
        st.info(
            "🎧 No listening attempts yet. Go to the "
            "**Listening Coach** page to complete your "
            "first listening track."
        )
    else:
        skill_labels = {
            "detail_accuracy": "Detail Accuracy",
            "main_idea": "Main Idea",
            "form_completion": "Form Completion"
        }

        # Latest attempt summary
        latest = listening_data["attempts"][-1]
        pct = latest.get("percentage", 0)
        total = latest.get("total_score", 0)
        maximum = latest.get("max_score", 0)

        st.subheader("🎯 Latest Listening Score")

        if pct >= 80:
            st.success(
                f"Latest attempt: **{total} / {maximum}** ({pct}%) 🎉"
            )
        elif pct >= 60:
            st.warning(
                f"Latest attempt: **{total} / {maximum}** ({pct}%) 👍"
            )
        else:
            st.error(
                f"Latest attempt: **{total} / {maximum}** ({pct}%) 📚"
            )

        # Skill accuracy scores
        averages = listening_data.get("skill_averages", {})
        if averages:
            cols = st.columns(len(averages))
            for i, (skill, avg) in enumerate(averages.items()):
                with cols[i]:
                    label = skill_labels.get(
                        skill,
                        skill.replace("_", " ").title()
                    )
                    latest_acc = latest.get(
                        "skill_accuracy", {}
                    ).get(skill, 0)
                    delta = round(latest_acc - avg, 1)
                    delta_str = (
                        f"{delta:+.1f}% vs avg"
                        if listening_data["total_attempts"] > 1
                        else None
                    )
                    st.metric(
                        label=label,
                        value=f"{latest_acc}%",
                        delta=delta_str
                    )

        # Score trend chart
        if listening_data["total_attempts"] > 1:
            st.markdown("---")
            st.subheader("📉 Listening Score Trends")
            st.caption(
                "Overall percentage score across attempts"
            )

            chart_data = {}
            overall_trend = listening_data["skill_trends"].get(
                "overall", []
            )
            if overall_trend:
                chart_data["Overall %"] = overall_trend

            for skill, label in skill_labels.items():
                trend = listening_data["skill_trends"].get(skill, [])
                if trend:
                    chart_data[label] = trend

            if chart_data:
                st.line_chart(chart_data)

        # Skill breakdown table
        st.markdown("---")
        st.subheader("📋 Skill Breakdown")

        best_skill = listening_data.get("best_skill")
        worst_skill = listening_data.get("worst_skill")

        rows = []
        for skill, avg in averages.items():
            label = skill_labels.get(
                skill, skill.replace("_", " ").title()
            )
            trend = listening_data["skill_trends"].get(skill, [])
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
            if skill == best_skill:
                tag = " 🏆"
            elif skill == worst_skill:
                tag = " ⚠️"

            rows.append({
                "Skill": label + tag,
                "Average Score": f"{avg}%",
                "Latest Score": f"{latest_val}%",
                "Trend": trend_icon
            })

        if rows:
            st.table(rows)

        # Recommended focus
        st.markdown("---")
        st.subheader("🎯 Recommended Listening Focus")

        if worst_skill:
            worst_label = skill_labels.get(
                worst_skill,
                worst_skill.replace("_", " ").title()
            )
            worst_avg = averages.get(worst_skill, 0)
            st.warning(
                f"Your coach recommends focusing on "
                f"**{worst_label}** in your listening practice. "
                f"Your average accuracy is **{worst_avg}%**."
            )

        # Attempt history
        st.markdown("---")
        st.subheader("📜 Listening Attempt History")

        for attempt in reversed(listening_data["attempts"]):
            with st.expander(
                f"Attempt {attempt['attempt_number']} — "
                f"Part {attempt['part']}: {attempt['track_title']} — "
                f"{attempt['total_score']}/{attempt['max_score']} "
                f"({attempt['percentage']}%) — "
                f"{attempt['created_at'][:16].replace('T', ' at ')}"
            ):
                skill_acc = attempt.get("skill_accuracy", {})
                if skill_acc:
                    cols = st.columns(len(skill_acc))
                    for i, (skill, acc) in enumerate(
                        skill_acc.items()
                    ):
                        label = skill_labels.get(
                            skill,
                            skill.replace("_", " ").title()
                        )
                        with cols[i]:
                            st.metric(label, f"{acc}%")

                if attempt["feedback"]:
                    st.markdown(
                        f"**Result:** {attempt['feedback']}"
                    )
