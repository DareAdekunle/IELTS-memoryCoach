import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.reading_service import (
    get_random_passage,
    get_all_passages_summary,
    get_passage_by_id,
    evaluate_reading_attempt
)
from app.services.memory_service import (
    get_relevant_memories,
    extract_reading_memories,
    save_reading_attempt,
    update_memories
)

st.set_page_config(
    page_title="Reading Coach",
    page_icon="📖",
    layout="wide"
)

st.title("📖 Reading Coach")
st.markdown("Read the passage carefully then answer all 10 questions.")
st.markdown("---")

# Always check for a profile first
if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning("👈 Please create your **Learner Profile** first before starting practice.")
    st.stop()

learner_id = st.session_state["learner_id"]

# ─── Memory panel ─────────────────────────────────────────────────────────────
memories = get_relevant_memories(learner_id, section="Reading", limit=3)

if memories:
    with st.expander("🧠 What your coach remembers about your reading", expanded=True):
        weaknesses = [m for m in memories if m["memory_type"] == "weakness"]
        strengths = [m for m in memories if m["memory_type"] == "strength"]

        if weaknesses:
            st.markdown("**Areas your coach is watching:**")
            for mem in weaknesses:
                confidence_pct = int(mem["confidence"] * 100)
                st.markdown(
                    f"⚠️ **{mem['skill']}** *({confidence_pct}% confidence)*: "
                    f"{mem['memory_text']}"
                )

        if strengths:
            st.markdown("**Your observed strengths:**")
            for mem in strengths:
                st.markdown(f"✅ **{mem['skill']}**: {mem['memory_text']}")
else:
    st.info("🧠 No reading memories yet — your coach will start learning about you after your first attempt.")

# ─── Initialise session state ─────────────────────────────────────────────────
if "reading_passage" not in st.session_state:
    st.session_state["reading_passage"] = None

if "reading_results" not in st.session_state:
    st.session_state["reading_results"] = None

if "reading_submitted" not in st.session_state:
    st.session_state["reading_submitted"] = False


# ─── PASSAGE SELECTION ────────────────────────────────────────────────────────
if st.session_state["reading_passage"] is None:

    st.subheader("Choose your passage")

    col1, col2 = st.columns(2)

    with col1:
        difficulty = st.selectbox(
            "Select difficulty level",
            ["Any", "Beginner", "Intermediate", "Advanced"]
        )

    with col2:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.markdown("&nbsp;", unsafe_allow_html=True)

        if st.button("🎲 Get a Passage", use_container_width=True):
            diff = None if difficulty == "Any" else difficulty.lower()
            try:
                passage = get_random_passage(difficulty=diff)
                st.session_state["reading_passage"] = passage
                st.session_state["reading_results"] = None
                st.session_state["reading_submitted"] = False
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    # Show all available passages as an alternative
    st.markdown("---")
    st.markdown("**Or choose a specific passage:**")

    summaries = get_all_passages_summary()
    for summary in summaries:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(f"**{summary['title']}**  \n{summary['topic']}")
        with col2:
            difficulty_colors = {
                "beginner": "🟢",
                "intermediate": "🟡",
                "advanced": "🔴"
            }
            icon = difficulty_colors.get(summary["difficulty"], "⚪")
            st.markdown(f"{icon} {summary['difficulty'].title()}")
        with col3:
            if st.button("Select", key=f"select_{summary['passage_id']}"):
                passage = get_passage_by_id(summary["passage_id"])
                st.session_state["reading_passage"] = passage
                st.session_state["reading_results"] = None
                st.session_state["reading_submitted"] = False
                st.rerun()

    st.stop()


# ─── RESULTS STATE ────────────────────────────────────────────────────────────
if st.session_state["reading_submitted"] and st.session_state["reading_results"]:

    results = st.session_state["reading_results"]
    passage = st.session_state["reading_passage"]

    st.subheader(f"📊 Results — {results['passage_title']}")

    # Overall score banner
    percentage = results["percentage"]
    total = results["total_score"]
    maximum = results["max_score"]

    if percentage >= 80:
        st.success(f"🎉 Excellent! You scored **{total} / {maximum}** ({percentage}%)")
    elif percentage >= 60:
        st.warning(f"👍 Good effort! You scored **{total} / {maximum}** ({percentage}%)")
    else:
        st.error(f"📚 Keep practising! You scored **{total} / {maximum}** ({percentage}%)")

    # Skill accuracy breakdown
    st.markdown("---")
    st.subheader("📈 Skill Breakdown")

    skill_labels = {
        "main_idea": "Main Idea",
        "detail_retrieval": "Detail Retrieval",
        "inference": "Inference",
        "vocabulary_in_context": "Vocabulary in Context",
        "true_false_ng": "True / False / Not Given"
    }

    skill_accuracy = results.get("skill_accuracy", {})
    if skill_accuracy:
        cols = st.columns(len(skill_accuracy))
        for i, (skill, accuracy) in enumerate(skill_accuracy.items()):
            with cols[i]:
                label = skill_labels.get(skill, skill.replace("_", " ").title())
                color = "🟢" if accuracy >= 80 else "🟡" if accuracy >= 50 else "🔴"
                st.metric(label=label, value=f"{color} {accuracy}%")

    # Question by question review
    st.markdown("---")
    st.subheader("📝 Question Review")

    for result in results["question_results"]:
        qtype = result["question_type"]
        is_correct = result["is_correct"]
        partial = result.get("partial_credit", False)

        # Header for each question
        if is_correct:
            icon = "✅"
            score_display = f"{result['score']} / {result['max_score']}"
        elif partial:
            icon = "🟡"
            score_display = f"{result['score']} / {result['max_score']}"
        else:
            icon = "❌"
            score_display = f"{result['score']} / {result['max_score']}"

        type_labels = {
            "multiple_choice": "Multiple Choice",
            "true_false_ng": "True / False / Not Given",
            "short_answer": "Short Answer"
        }
        type_label = type_labels.get(qtype, qtype)

        with st.expander(
            f"{icon} {result['question_id'].upper()} — {type_label} — {score_display}",
            expanded=not is_correct
        ):
            st.markdown(f"**Question:** {result['question']}")
            st.markdown(f"**Your answer:** {result['learner_answer'] or '*No answer given*'}")

            if not is_correct or partial:
                st.markdown(f"**Correct answer:** {result['correct_answer']}")
                st.info(f"💡 **Explanation:** {result['feedback']}")
            else:
                st.success("Well done — correct answer!")

    # Action buttons
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Try Another Passage", use_container_width=True):
            st.session_state["reading_passage"] = None
            st.session_state["reading_results"] = None
            st.session_state["reading_submitted"] = False
            st.rerun()

    with col2:
        if st.button("🔁 Retry This Passage", use_container_width=True):
            st.session_state["reading_results"] = None
            st.session_state["reading_submitted"] = False
            st.rerun()

    st.stop()


# ─── READING AND ANSWERING STATE ──────────────────────────────────────────────
passage = st.session_state["reading_passage"]

# Passage header
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.subheader(f"📄 {passage['title']}")
with col2:
    difficulty_colors = {
        "beginner": "🟢",
        "intermediate": "🟡",
        "advanced": "🔴"
    }
    icon = difficulty_colors.get(passage["difficulty"], "⚪")
    st.markdown(f"**Difficulty:** {icon} {passage['difficulty'].title()}")
with col3:
    if st.button("Choose Different Passage"):
        st.session_state["reading_passage"] = None
        st.session_state["reading_results"] = None
        st.session_state["reading_submitted"] = False
        st.rerun()

st.markdown("---")

# Two column layout — passage on left, questions on right
left_col, right_col = st.columns([1, 1])

# ─── LEFT: Passage ────────────────────────────────────────────────────────────
with left_col:
    st.markdown("### 📖 Read the Passage")
    st.markdown(
        f"""
        <div style='
            background-color: #1e2130;
            padding: 20px;
            border-radius: 10px;
            line-height: 1.8;
            font-size: 15px;
            height: 600px;
            overflow-y: auto;
            border: 1px solid #2a2f45;
        '>
        {passage['passage'].replace(chr(10), '<br><br>')}
        </div>
        """,
        unsafe_allow_html=True
    )

# ─── RIGHT: Questions ─────────────────────────────────────────────────────────
with right_col:
    st.markdown("### ✏️ Answer the Questions")
    st.caption("Answer all 10 questions then click Submit at the bottom.")

    learner_answers = {}
    questions = passage["questions"]

    for i, question in enumerate(questions):
        qid = question["question_id"]
        qtype = question["question_type"]

        st.markdown(f"**Q{i+1}. {question['question']}**")

        if qtype == "multiple_choice":
            options = question.get("options", {})
            option_list = [f"{k}: {v}" for k, v in options.items()]

            selected = st.radio(
                label=f"Select answer for Q{i+1}",
                options=option_list,
                key=f"mc_{qid}",
                label_visibility="collapsed"
            )

            # Extract just the letter from "A: some option text"
            if selected:
                learner_answers[qid] = selected[0]

        elif qtype == "true_false_ng":
            selected = st.selectbox(
                label=f"Select answer for Q{i+1}",
                options=["-- Select --", "True", "False", "Not Given"],
                key=f"tfng_{qid}",
                label_visibility="collapsed"
            )

            if selected != "-- Select --":
                learner_answers[qid] = selected

        elif qtype == "short_answer":
            answer = st.text_area(
                label=f"Your answer for Q{i+1}",
                key=f"sa_{qid}",
                height=80,
                placeholder="Write your answer here...",
                label_visibility="collapsed"
            )

            if answer.strip():
                learner_answers[qid] = answer.strip()

        st.markdown("---")

    # Check how many questions have been answered
    answered = len(learner_answers)
    total_questions = len(questions)

    if answered < total_questions:
        st.warning(
            f"⚠️ You have answered {answered} / {total_questions} questions. "
            f"Please answer all questions before submitting."
        )
    else:
        st.success(f"✅ All {total_questions} questions answered — ready to submit!")

    submitted = st.button(
        "Submit All Answers ✅",
        disabled=answered < total_questions,
        use_container_width=True
    )

    if submitted:
        with st.spinner(
            "Checking your answers... Short answer questions are being "
            "evaluated by your coach. This may take a moment."
        ):
            try:
                # Step 1: Evaluate all answers
                results = evaluate_reading_attempt(
                    passage=passage,
                    learner_answers=learner_answers
                )
                st.session_state["reading_results"] = results
                st.session_state["reading_submitted"] = True

                # Step 2: Save the attempt to the database
                save_reading_attempt(
                    learner_id=learner_id,
                    attempt_result=results
                )

            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.stop()

        # Step 3: Extract memories from this attempt
        with st.spinner("Coach is updating your reading memory profile..."):
            try:
                extract_reading_memories(
                    learner_id=learner_id,
                    attempt_result=results
                )

                # Step 4: Update existing memories with new evidence
                update_summary = update_memories(
                    learner_id=learner_id,
                    section="Reading",
                    score_result={
                        "scores": results.get("skill_accuracy", {}),
                        "strengths": [
                            f"{skill} accuracy: {acc}%"
                            for skill, acc in results.get("skill_accuracy", {}).items()
                            if acc >= 80
                        ],
                        "weaknesses": [
                            f"{skill} accuracy: {acc}%"
                            for skill, acc in results.get("skill_accuracy", {}).items()
                            if acc < 60
                        ],
                        "overall_feedback": (
                            f"Score: {results['total_score']} / "
                            f"{results['max_score']} ({results['percentage']}%)"
                        )
                    }
                )

                archived = update_summary.get("archived", 0)
                if archived > 0:
                    st.success(
                        f"🎉 Great progress! {archived} reading skill(s) "
                        f"have been archived as mastered."
                    )

            except Exception as e:
                st.warning(f"Results saved but memory update had an issue: {e}")

        st.rerun()
