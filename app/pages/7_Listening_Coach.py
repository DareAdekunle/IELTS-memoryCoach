import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.listening_service import (
    get_all_tracks_summary,
    get_track_by_id,
    get_random_track,
    generate_track_audio,
    evaluate_listening_attempt
)
from app.services.memory_service import (
    get_relevant_memories,
    extract_listening_memories,
    save_listening_attempt,
    update_memories
)

st.set_page_config(
    page_title="Listening Coach",
    page_icon="🎧",
    layout="wide"
)

st.title("🎧 Listening Coach")
st.markdown("Preview the questions while Cherry prepares your audio.")
st.markdown("---")

# ─── Profile check ────────────────────────────────────────────────────────────
if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning(
        "👈 Please create your **Learner Profile** first "
        "before starting practice."
    )
    st.stop()

learner_id = st.session_state["learner_id"]

# ─── Session state defaults ───────────────────────────────────────────────────
defaults = {
    "listening_track": None,
    "listening_audio_bytes": None,
    "listening_audio_ready": False,
    "listening_phase": "selection",
    "listening_results": None,
    "listening_answers": {}
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_session():
    for key, val in defaults.items():
        st.session_state[key] = val


# ══════════════════════════════════════════════════════════════════════════════
# STATE 1 — RESULTS
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["listening_phase"] == "results":
    results = st.session_state["listening_results"]
    track = st.session_state["listening_track"]

    st.subheader(
        f"📊 Results — Part {track['part']}: {track['title']}"
    )

    percentage = results["percentage"]
    total = results["total_score"]
    maximum = results["max_score"]

    if percentage >= 80:
        st.success(
            f"🎉 Excellent! You scored **{total} / {maximum}** ({percentage}%)"
        )
    elif percentage >= 60:
        st.warning(
            f"👍 Good effort! You scored **{total} / {maximum}** ({percentage}%)"
        )
    else:
        st.error(
            f"📚 Keep practising! You scored **{total} / {maximum}** ({percentage}%)"
        )

    st.markdown("---")
    st.subheader("📈 Skill Breakdown")

    skill_labels = {
        "detail_accuracy": "Detail Accuracy",
        "main_idea": "Main Idea",
        "form_completion": "Form Completion"
    }

    skill_accuracy = results.get("skill_accuracy", {})
    if skill_accuracy:
        cols = st.columns(len(skill_accuracy))
        for i, (skill, accuracy) in enumerate(skill_accuracy.items()):
            with cols[i]:
                label = skill_labels.get(
                    skill, skill.replace("_", " ").title()
                )
                color = (
                    "🟢" if accuracy >= 80
                    else "🟡" if accuracy >= 50
                    else "🔴"
                )
                st.metric(label=label, value=f"{color} {accuracy}%")

    st.markdown("---")
    st.subheader("📝 Question Review")

    for result in results["question_results"]:
        qtype = result["question_type"]
        is_correct = result["is_correct"]
        icon = "✅" if is_correct else "❌"
        score_display = f"{result['score']} / {result['max_score']}"

        type_labels = {
            "multiple_choice": "Multiple Choice",
            "form_completion": "Form Completion",
            "short_answer": "Short Answer"
        }
        type_label = type_labels.get(qtype, qtype)

        with st.expander(
            f"{icon} {result['question_id'].upper()} — "
            f"{type_label} — {score_display}",
            expanded=not is_correct
        ):
            st.markdown(f"**Question:** {result['question']}")

            if qtype == "multiple_choice" and result.get("options"):
                for letter, text in result["options"].items():
                    st.markdown(f"  {letter}: {text}")

            st.markdown(
                f"**Your answer:** "
                f"{result['learner_answer'] or '*No answer given*'}"
            )

            if not is_correct:
                st.markdown(
                    f"**Correct answer:** {result['correct_answer']}"
                )
                st.info(f"💡 **Explanation:** {result['feedback']}")
            else:
                st.success("Well done — correct answer!")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Try Another Track", use_container_width=True):
            reset_session()
            st.rerun()
    with col2:
        if st.button("🔁 Retry This Track", use_container_width=True):
            track = st.session_state["listening_track"]
            reset_session()
            st.session_state["listening_track"] = track
            st.session_state["listening_phase"] = "preview_and_load"
            st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STATE 2 — SELECTION
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["listening_phase"] == "selection":

    memories = get_relevant_memories(
        learner_id, section="Listening", limit=3
    )
    if memories:
        with st.expander(
            "🧠 What your coach remembers about your listening",
            expanded=True
        ):
            for mem in memories:
                icon = "⚠️" if mem["memory_type"] == "weakness" else "✅"
                confidence_pct = int(mem["confidence"] * 100)
                st.markdown(
                    f"{icon} **{mem['skill']}** "
                    f"*({confidence_pct}% confidence)*: "
                    f"{mem['memory_text']}"
                )
    else:
        st.info(
            "🧠 No listening memories yet — your coach will start "
            "learning about you after your first attempt."
        )

    st.markdown("---")
    st.subheader("Choose your listening track")

    col1, col2, col3 = st.columns(3)
    with col1:
        difficulty = st.selectbox(
            "Difficulty",
            ["Any", "Beginner", "Intermediate", "Advanced"]
        )
    with col2:
        part = st.selectbox(
            "IELTS Part",
            ["Any", "Part 1", "Part 2", "Part 3", "Part 4"]
        )
    with col3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("🎲 Get a Random Track", use_container_width=True):
            diff = None if difficulty == "Any" else difficulty.lower()
            part_num = (
                None if part == "Any"
                else int(part.split()[-1])
            )
            try:
                track = get_random_track(
                    difficulty=diff, part=part_num
                )
                st.session_state["listening_track"] = track
                st.session_state["listening_phase"] = "preview_and_load"
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown("**Or choose a specific track:**")

    summaries = get_all_tracks_summary()
    for summary in summaries:
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.markdown(
                f"**{summary['title']}**  \n"
                f"{summary['context'][:80]}..."
            )
        with col2:
            icons = {
                "beginner": "🟢",
                "intermediate": "🟡",
                "advanced": "🔴"
            }
            icon = icons.get(summary["difficulty"], "⚪")
            st.markdown(f"{icon} {summary['difficulty'].title()}")
        with col3:
            st.markdown(f"Part {summary['part']}")
        with col4:
            if st.button(
                "Select",
                key=f"select_{summary['track_id']}"
            ):
                track = get_track_by_id(summary["track_id"])
                st.session_state["listening_track"] = track
                st.session_state["listening_phase"] = "preview_and_load"
                st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STATE 3 — PREVIEW QUESTIONS + GENERATE AUDIO SIMULTANEOUSLY
# Questions shown immediately while Cherry prepares audio in background
# When learner clicks ready — audio plays immediately if ready
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["listening_phase"] == "preview_and_load":
    track = st.session_state["listening_track"]

    st.subheader(f"📋 Part {track['part']}: {track['title']}")
    st.markdown(f"**{track['context']}**")
    st.markdown("---")

    # Two column layout
    # Left: questions to preview
    # Right: audio preparation status
    col_questions, col_status = st.columns([2, 1])

    with col_status:
        st.markdown("### 🎙️ Audio Status")

        # Check if audio is already ready from a previous load
        if st.session_state["listening_audio_ready"]:
            st.success(
                "✅ Audio is ready!\n\n"
                "Finish reading the questions then click "
                "**Start Listening** when you are ready."
            )
        else:
            # Generate audio now while learner reads questions
            st.info(
                "⏳ Cherry is preparing your audio...\n\n"
                "Use this time to read through all the questions "
                "carefully. Know what to listen for before the "
                "audio starts — this is a key IELTS strategy!"
            )

            with st.spinner("Generating audio..."):
                audio_result = generate_track_audio(track)

            if audio_result["success"]:
                st.session_state["listening_audio_bytes"] = (
                    audio_result["audio_bytes"]
                )
                st.session_state["listening_audio_ready"] = True
                st.success(
                    "✅ Audio is ready!\n\n"
                    "Finish reading the questions then click "
                    "**Start Listening** when you are ready."
                )
            else:
                st.error(
                    f"Could not generate audio: "
                    f"{audio_result['error']}"
                )
                if st.button("← Try Again"):
                    reset_session()
                    st.rerun()
                st.stop()

        st.markdown("---")
        st.markdown("**📌 IELTS Listening Tips**")
        st.markdown(
            "- Read questions carefully before listening\n"
            "- Underline key words in each question\n"
            "- Think about what type of answer is needed\n"
            "- Listen for synonyms — the audio may use "
            "different words than the questions\n"
            "- Do not spend too long on one question"
        )

        st.markdown("---")

        # Only show Start button when audio is ready
        if st.session_state["listening_audio_ready"]:
            if st.button(
                "▶️ Start Listening",
                use_container_width=True,
                type="primary"
            ):
                st.session_state["listening_phase"] = "listening"
                st.rerun()

        if st.button(
            "← Choose Different Track",
            use_container_width=True
        ):
            reset_session()
            st.rerun()

    with col_questions:
        st.markdown("### 📝 Read the Questions First")
        st.caption(
            "Study these carefully before the audio starts. "
            "In the real IELTS test you get 30-45 seconds to "
            "preview questions."
        )
        st.markdown("")

        questions = track["questions"]
        type_labels = {
            "multiple_choice": "Multiple Choice",
            "form_completion": "Form Completion",
            "short_answer": "Short Answer"
        }

        for i, question in enumerate(questions):
            qtype = question["question_type"]
            type_label = type_labels.get(qtype, qtype)

            st.markdown(
                f"**Q{i+1}. [{type_label}]** {question['question']}"
            )

            if qtype == "multiple_choice":
                options = question.get("options", {})
                for letter, text in options.items():
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{letter}: {text}")

            st.markdown("")

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STATE 4 — LISTENING AND ANSWERING
# Audio at top — plays once — learner answers while listening
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["listening_phase"] == "listening":
    track = st.session_state["listening_track"]
    audio_bytes = st.session_state["listening_audio_bytes"]

    st.subheader(
        f"🎧 Part {track['part']}: {track['title']} — Listen and Answer"
    )

    st.error(
        "🔴 **EXAM CONDITIONS** — Press play and answer the questions "
        "as you listen. The recording plays once only — "
        "just like the real IELTS test."
    )

    st.markdown("---")

    # Audio player fixed at top
    st.markdown("### 🔊 Recording — Play Once")
    st.audio(audio_bytes, format="audio/wav")
    st.caption(
        "▶️ Press play now and answer the questions below as you listen."
    )

    st.markdown("---")
    st.markdown("### ✏️ Answer While Listening")

    questions = track["questions"]
    learner_answers = {}
    all_answered = True

    for i, question in enumerate(questions):
        qid = question["question_id"]
        qtype = question["question_type"]

        st.markdown(f"**Q{i+1}. {question['question']}**")

        if qtype == "multiple_choice":
            options = question.get("options", {})
            option_list = [
                f"{k}: {v}" for k, v in options.items()
            ]
            selected = st.radio(
                label=f"Select answer for Q{i+1}",
                options=option_list,
                key=f"mc_{qid}",
                label_visibility="collapsed"
            )
            if selected:
                learner_answers[qid] = selected[0]

        elif qtype in ["form_completion", "short_answer"]:
            placeholder = (
                "Fill in the missing information..."
                if qtype == "form_completion"
                else "Write your answer here..."
            )
            answer = st.text_input(
                label=f"Answer for Q{i+1}",
                key=f"text_{qid}",
                placeholder=placeholder,
                label_visibility="collapsed"
            )
            if answer.strip():
                learner_answers[qid] = answer.strip()
            else:
                all_answered = False

        st.markdown("---")

    answered_count = len(learner_answers)
    total_questions = len(questions)

    if answered_count < total_questions:
        st.warning(
            f"⚠️ Answered: {answered_count} / {total_questions}"
        )
    else:
        st.success(
            f"✅ All {total_questions} questions answered!"
        )

    submitted = st.button(
        "Submit Answers ✅",
        disabled=answered_count < total_questions,
        use_container_width=True
    )

    if submitted:
        with st.spinner("Checking your answers..."):
            try:
                # Step 1: Evaluate all answers
                results = evaluate_listening_attempt(
                    track=track,
                    learner_answers=learner_answers
                )

                # Step 2: Save the attempt to the database
                save_listening_attempt(
                    learner_id=learner_id,
                    attempt_result=results
                )

                st.session_state["listening_results"] = results
                st.session_state["listening_phase"] = "results"

            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.stop()

        # Step 3: Extract memories from this attempt
        with st.spinner(
            "Coach is updating your listening memory profile..."
        ):
            try:
                extract_listening_memories(
                    learner_id=learner_id,
                    attempt_result=results
                )

                # Step 4: Update existing memories
                skill_accuracy = results.get("skill_accuracy", {})
                update_summary = update_memories(
                    learner_id=learner_id,
                    section="Listening",
                    score_result={
                        "scores": {
                            skill: acc / 20
                            for skill, acc in skill_accuracy.items()
                        },
                        "strengths": [
                            f"{skill} accuracy: {acc}%"
                            for skill, acc in skill_accuracy.items()
                            if acc >= 80
                        ],
                        "weaknesses": [
                            f"{skill} accuracy: {acc}%"
                            for skill, acc in skill_accuracy.items()
                            if acc < 60
                        ],
                        "overall_feedback": (
                            f"Score: {results['total_score']} / "
                            f"{results['max_score']} "
                            f"({results['percentage']}%)"
                        )
                    }
                )

                archived = update_summary.get("archived", 0)
                if archived > 0:
                    st.success(
                        f"🎉 Great progress! {archived} listening "
                        f"skill(s) archived as mastered."
                    )

            except Exception as e:
                st.warning(
                    f"Results saved but memory update had "
                    f"an issue: {e}"
                )

        st.rerun()
