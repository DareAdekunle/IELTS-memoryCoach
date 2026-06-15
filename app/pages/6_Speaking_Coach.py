import streamlit as st
import sys
import os
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.speaking_service import (
    get_random_prompt_set,
    get_all_prompt_sets_summary,
    get_prompt_set_by_id,
    get_session_structure
)

from app.services.asr_service import transcribe_audio_bytes
from app.services.speaking_evaluator_service import evaluate_speaking_attempt
from app.services.memory_service import (
    get_relevant_memories, 
    extract_speaking_memories, 
    save_speaking_attempt, 
    update_memories
)
try:
    from audio_recorder_streamlit import audio_recorder
    AUDIO_RECORDER_AVAILABLE = True
except ImportError:
    AUDIO_RECORDER_AVAILABLE = False

st.set_page_config(
    page_title="Speaking Coach",
    page_icon="🎤",
    layout="wide"
)

st.title("🎤 Speaking Coach")
st.markdown("Complete all three parts of the IELTS speaking test.")
st.markdown("---")

# ─── Profile check ────────────────────────────────────────────────────────────
if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning("👈 Please create your **Learner Profile** first before starting practice.")
    st.stop()

learner_id = st.session_state["learner_id"]

# ─── Session state defaults ───────────────────────────────────────────────────
defaults = {
    "speaking_prompt_set": None,
    "speaking_current_part": None,
    "speaking_part1_transcriptions": {},
    "speaking_part2_transcription": "",
    "speaking_part3_transcriptions": {},
    "speaking_results": None,
    "speaking_submitted": False,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_session():
    """Clears all speaking session state."""
    for key, val in defaults.items():
        st.session_state[key] = val


# ─── Audio input component ────────────────────────────────────────────────────
def render_audio_input(label: str, key: str) -> bytes | None:
    """
    Renders a microphone recorder tab and a file upload tab.
    Returns raw audio bytes if the learner provides audio.
    Returns None if no audio has been provided yet.

    The recorder uses audio-recorder-streamlit which returns
    bytes directly. The file uploader also returns bytes.
    Both are passed to the ASR service for transcription.
    """
    st.markdown(f"**{label}**")

    if AUDIO_RECORDER_AVAILABLE:
        tab1, tab2 = st.tabs(["🎙️ Record", "📁 Upload File"])

        with tab1:
            st.caption(
                "Click the red microphone to start. "
                "Click again to stop, or it stops automatically "
                "after 3 seconds of silence."
            )
            audio_bytes = audio_recorder(
                text="",
                recording_color="#e8b62c",
                neutral_color="#cc0000",
                icon_name="microphone",
                icon_size="2x",
                pause_threshold=3.0,
                sample_rate=16_000,
                key=f"recorder_{key}"
            )
            # Filter out accidental clicks — under 1KB is silence
            if audio_bytes and len(audio_bytes) > 1000:
                return audio_bytes

        with tab2:
            st.caption("Upload a .wav, .mp3, .m4a or .webm recording.")
            uploaded = st.file_uploader(
                "Upload audio",
                type=["wav", "mp3", "m4a", "webm", "ogg"],
                key=f"upload_{key}",
                label_visibility="collapsed"
            )
            if uploaded:
                return uploaded.read()

    else:
        # Microphone recorder not available — file upload only
        st.caption(
            "💡 Tip: Install audio-recorder-streamlit for microphone support. "
            "For now please upload an audio recording."
        )
        uploaded = st.file_uploader(
            "Upload audio recording",
            type=["wav", "mp3", "m4a", "webm", "ogg"],
            key=f"upload_{key}",
            label_visibility="collapsed"
        )
        if uploaded:
            return uploaded.read()

    return None


# ══════════════════════════════════════════════════════════════════════════════
# STATE 1 — RESULTS
# Show this if the learner has already submitted the full session
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["speaking_submitted"] and st.session_state["speaking_results"]:
    results = st.session_state["speaking_results"]
    prompt_set = st.session_state["speaking_prompt_set"]
    session = get_session_structure(prompt_set)

    st.subheader(f"📊 Speaking Test Results — {prompt_set['topic']}")

    # ── Examiner audio feedback ──────────────────────────────────────────────
    if results.get("audio_bytes"):
        st.markdown("### 🎧 Listen to Your Examiner Feedback")
        st.audio(results["audio_bytes"], format="audio/wav")
        st.caption("Cherry is reading your examiner feedback aloud.")
    else:
        st.warning("Audio feedback was not generated. See written feedback below.")

    st.markdown("---")

    # ── Written feedback ─────────────────────────────────────────────────────
    st.markdown("### 💬 Examiner Feedback")
    st.info(results["feedback_text"])

    # ── Band scores ──────────────────────────────────────────────────────────
    scores = results.get("scores", {})
    if scores:
        st.markdown("---")
        st.markdown("### 📊 Band Scores")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric(
                "Fluency & Coherence",
                f"{scores.get('fluency_coherence', '?')} / 9"
            )
        with col2:
            st.metric(
                "Lexical Resource",
                f"{scores.get('lexical_resource', '?')} / 9"
            )
        with col3:
            st.metric(
                "Grammatical Range",
                f"{scores.get('grammatical_range', '?')} / 9"
            )
        with col4:
            st.metric(
                "Pronunciation",
                f"{scores.get('pronunciation_clarity', '?')} / 9"
            )
        with col5:
            st.metric(
                "Overall Band",
                f"{scores.get('overall_band', '?')}"
            )

        # ── Part by part comments ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📝 Part by Part Comments")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Part 1 — Personal Questions**")
            st.markdown(scores.get("part1_comment", "—"))
        with col2:
            st.markdown("**Part 2 — Long Turn**")
            st.markdown(scores.get("part2_comment", "—"))
        with col3:
            st.markdown("**Part 3 — Discussion**")
            st.markdown(scores.get("part3_comment", "—"))

        # ── Strengths and weaknesses ─────────────────────────────────────────
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### ✅ Strengths")
            for s in scores.get("strengths", []):
                st.markdown(f"- {s}")
        with col2:
            st.markdown("### ⚠️ Areas to Improve")
            for w in scores.get("weaknesses", []):
                st.markdown(f"- {w}")

    # ── Transcription review ─────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📄 Review Your Transcriptions"):
        st.markdown("**Part 1 Responses**")
        for i, q in enumerate(session["part1"]["questions"]):
            st.markdown(f"*Q: {q}*")
            response = results.get(
                "part1_responses", {}
            ).get(str(i), "[No response]")
            st.markdown(f"A: {response}")
            st.markdown("")

        st.markdown("**Part 2 Response**")
        st.markdown(f"*{session['part2']['title']}*")
        st.markdown(results.get("part2_response", "[No response]"))
        st.markdown("")

        st.markdown("**Part 3 Responses**")
        for i, q in enumerate(session["part3"]["questions"]):
            st.markdown(f"*Q: {q}*")
            response = results.get(
                "part3_responses", {}
            ).get(str(i), "[No response]")
            st.markdown(f"A: {response}")
            st.markdown("")

    # ── Action buttons ───────────────────────────────────────────────────────
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Try Another Topic", use_container_width=True):
            reset_session()
            st.rerun()
    with col2:
        if st.button("🔁 Retry This Topic", use_container_width=True):
            saved_prompt_set = st.session_state["speaking_prompt_set"]
            reset_session()
            st.session_state["speaking_prompt_set"] = saved_prompt_set
            st.session_state["speaking_current_part"] = "part1"
            st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STATE 2 — TOPIC SELECTION
# Show this if no prompt set has been chosen yet
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["speaking_prompt_set"] is None:

    # Memory panel
    memories = get_relevant_memories(learner_id, section="Speaking", limit=3)

    if memories:
        with st.expander(
            "🧠 What your coach remembers about your speaking",
            expanded=True
        ):
            weaknesses = [m for m in memories if m["memory_type"] == "weakness"]
            strengths = [m for m in memories if m["memory_type"] == "strength"]

            if weaknesses:
                st.markdown("**Areas your coach is watching:**")
                for mem in weaknesses:
                    confidence_pct = int(mem["confidence"] * 100)
                    st.markdown(
                        f"⚠️ **{mem['skill']}** "
                        f"*({confidence_pct}% confidence)*: "
                        f"{mem['memory_text']}"
                    )
            if strengths:
                st.markdown("**Your observed strengths:**")
                for mem in strengths:
                    st.markdown(
                        f"✅ **{mem['skill']}**: {mem['memory_text']}"
                    )
    else:
        st.info(
            "🧠 No speaking memories yet — your coach will start "
            "learning about you after your first attempt."
        )

    st.markdown("---")
    st.subheader("Choose your speaking topic")

    col1, col2 = st.columns(2)
    with col1:
        difficulty = st.selectbox(
            "Select difficulty",
            ["Any", "Beginner", "Intermediate", "Advanced"]
        )
    with col2:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("🎲 Get a Random Topic", use_container_width=True):
            diff = None if difficulty == "Any" else difficulty.lower()
            try:
                prompt_set = get_random_prompt_set(difficulty=diff)
                st.session_state["speaking_prompt_set"] = prompt_set
                st.session_state["speaking_current_part"] = "part1"
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown("**Or choose a specific topic:**")

    summaries = get_all_prompt_sets_summary()
    for summary in summaries:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(
                f"**{summary['topic']}**  \n"
                f"Part 2: *{summary['part2_title']}*"
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
            if st.button(
                "Select",
                key=f"select_{summary['prompt_set_id']}"
            ):
                prompt_set = get_prompt_set_by_id(
                    summary["prompt_set_id"]
                )
                st.session_state["speaking_prompt_set"] = prompt_set
                st.session_state["speaking_current_part"] = "part1"
                st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STATE 3 — ACTIVE SPEAKING SESSION
# Learner is working through Part 1, 2 or 3
# ══════════════════════════════════════════════════════════════════════════════
prompt_set = st.session_state["speaking_prompt_set"]
session = get_session_structure(prompt_set)
current_part = st.session_state["speaking_current_part"]

# ── Session header and progress ───────────────────────────────────────────────
st.markdown(
    f"**Topic:** {session['topic']} · "
    f"**Difficulty:** {session['difficulty'].title()}"
)

parts = ["part1", "part2", "part3"]
part_labels = [
    "Part 1 — Personal Questions",
    "Part 2 — Long Turn",
    "Part 3 — Discussion"
]
current_index = parts.index(current_part) if current_part in parts else 0
progress = current_index / 3
st.progress(progress)
st.markdown(f"**Now: {part_labels[current_index]}**")
st.markdown("---")

# ── Two column layout: progress on left, content on right ────────────────────
col_left, col_right = st.columns([1, 3])

with col_left:
    st.markdown("**Progress**")
    for i, label in enumerate(part_labels):
        if i < current_index:
            st.markdown(f"✅ {label}")
        elif i == current_index:
            st.markdown(f"▶️ **{label}**")
        else:
            st.markdown(f"⬜ {label}")

    st.markdown("---")
    if st.button("← Start Over", use_container_width=True):
        reset_session()
        st.rerun()

with col_right:

    # ══════════════════════════════════════════════════════════════════════════
    # PART 1 — Personal Questions
    # ══════════════════════════════════════════════════════════════════════════
    if current_part == "part1":
        st.markdown("### 🗣️ Part 1 — Personal Questions")
        st.markdown(
            "Answer each question naturally as if speaking to an examiner. "
            "Aim for 2-3 sentences per answer."
        )
        st.markdown("---")

        questions = session["part1"]["questions"]
        all_answered = True

        for i, question in enumerate(questions):
            st.markdown(f"**Q{i+1}: {question}**")

            # Check if this question already has a transcription
            existing = st.session_state[
                "speaking_part1_transcriptions"
            ].get(str(i), "")

            if existing:
                # Already transcribed — show it with option to re-record
                st.success(f"✅ Transcribed:")
                st.markdown(f"*{existing}*")
                if st.button(
                    f"🔄 Re-record Q{i+1}",
                    key=f"rerecord_p1_{i}"
                ):
                    st.session_state[
                        "speaking_part1_transcriptions"
                    ].pop(str(i), None)
                    st.rerun()
            else:
                # Not yet answered
                all_answered = False
                audio_bytes = render_audio_input(
                    label=f"Your answer to Q{i+1}",
                    key=f"p1_q{i}"
                )

                if audio_bytes:
                    with st.spinner(
                        f"Transcribing Q{i+1}..."
                    ):
                        result = transcribe_audio_bytes(audio_bytes)
                        if result["success"]:
                            st.session_state[
                                "speaking_part1_transcriptions"
                            ][str(i)] = result["text"]
                            st.rerun()
                        else:
                            st.error(
                                f"Transcription failed: {result['error']}"
                            )

            st.markdown("---")

        # Progress counter
        answered_count = len(
            st.session_state["speaking_part1_transcriptions"]
        )
        st.caption(
            f"Answered: {answered_count} / {len(questions)} questions"
        )

        # Only show continue button when all questions answered
        if all_answered:
            st.success("✅ All Part 1 questions answered!")
            if st.button(
                "Continue to Part 2 →",
                use_container_width=True
            ):
                st.session_state["speaking_current_part"] = "part2"
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PART 2 — Long Turn Monologue
    # ══════════════════════════════════════════════════════════════════════════
    elif current_part == "part2":
        st.markdown("### 🗣️ Part 2 — Long Turn")
        st.markdown(
            "Read the cue card carefully. You have **1 minute to prepare** "
            "then speak for **1-2 minutes** covering all the bullet points."
        )
        st.markdown("---")

        # Display the cue card
        st.markdown("#### 📋 Your Cue Card")
        st.info(session["part2"]["cue_card"])
        st.markdown("---")

        # Check if Part 2 already has a transcription
        existing_p2 = st.session_state["speaking_part2_transcription"]

        if existing_p2:
            st.success("✅ Part 2 response recorded and transcribed:")
            st.markdown(f"*{existing_p2}*")
            st.markdown("")

            if st.button("🔄 Re-record Part 2"):
                st.session_state["speaking_part2_transcription"] = ""
                st.rerun()

            st.markdown("---")
            if st.button(
                "Continue to Part 3 →",
                use_container_width=True
            ):
                st.session_state["speaking_current_part"] = "part3"
                st.rerun()

        else:
            st.markdown("#### 🎙️ Record Your Response")
            st.caption(
                "Speak for 1-2 minutes. Cover who, what, when, and why "
                "as shown on the cue card."
            )

            audio_bytes = render_audio_input(
                label="Your Part 2 monologue",
                key="part2_main"
            )

            if audio_bytes:
                with st.spinner(
                    "Transcribing your Part 2 response... "
                    "Longer recordings may take a moment."
                ):
                    result = transcribe_audio_bytes(audio_bytes)
                    if result["success"]:
                        st.session_state[
                            "speaking_part2_transcription"
                        ] = result["text"]
                        st.rerun()
                    else:
                        st.error(
                            f"Transcription failed: {result['error']}"
                        )

    # ══════════════════════════════════════════════════════════════════════════
    # PART 3 — Discussion Questions
    # ══════════════════════════════════════════════════════════════════════════
    elif current_part == "part3":
        st.markdown("### 🗣️ Part 3 — Discussion")
        st.markdown(
            "Give extended answers to these discussion questions. "
            "Give your opinion and support it with reasons and examples."
        )
        st.markdown("---")

        questions = session["part3"]["questions"]
        all_answered = True

        for i, question in enumerate(questions):
            st.markdown(f"**Q{i+1}: {question}**")

            existing = st.session_state[
                "speaking_part3_transcriptions"
            ].get(str(i), "")

            if existing:
                st.success(f"✅ Transcribed:")
                st.markdown(f"*{existing}*")
                if st.button(
                    f"🔄 Re-record Q{i+1}",
                    key=f"rerecord_p3_{i}"
                ):
                    st.session_state[
                        "speaking_part3_transcriptions"
                    ].pop(str(i), None)
                    st.rerun()
            else:
                all_answered = False
                audio_bytes = render_audio_input(
                    label=f"Your answer to Q{i+1}",
                    key=f"p3_q{i}"
                )

                if audio_bytes:
                    with st.spinner(f"Transcribing Q{i+1}..."):
                        result = transcribe_audio_bytes(audio_bytes)
                        if result["success"]:
                            st.session_state[
                                "speaking_part3_transcriptions"
                            ][str(i)] = result["text"]
                            st.rerun()
                        else:
                            st.error(
                                f"Transcription failed: {result['error']}"
                            )

            st.markdown("---")

        answered_count = len(
            st.session_state["speaking_part3_transcriptions"]
        )
        st.caption(
            f"Answered: {answered_count} / {len(questions)} questions"
        )

        if all_answered:
            st.success(
                "✅ All three parts complete — ready to submit!"
            )

            # Load memories to pass to evaluator
            memories = get_relevant_memories(
                learner_id, section="Speaking", limit=5
            )

            if st.button(
                "Submit for Examiner Feedback 🎤",
                use_container_width=True
            ):
                with st.spinner(
                    "Your examiner is reviewing all three parts and "
                    "Cherry is preparing your spoken feedback. "
                    "This may take 30-60 seconds..."
                ):
                    try:
                        # Step 1: Evaluate the full speaking session
                        results = evaluate_speaking_attempt(
                            prompt_set=prompt_set,
                            part1_responses=st.session_state[
                                "speaking_part1_transcriptions"
                            ],
                            part2_response=st.session_state[
                                "speaking_part2_transcription"
                            ],
                            part3_responses=st.session_state[
                                "speaking_part3_transcriptions"
                            ],
                            memories=memories
                        )

                        if not results["success"]:
                            st.error(
                                f"Evaluation failed: {results['error']}"
                            )
                            st.stop()

                        # Step 2: Save the attempt to the database
                        save_speaking_attempt(
                            learner_id=learner_id,
                            attempt_result=results
                        )

                        # Step 3: Store results in session state
                        st.session_state["speaking_results"] = results
                        st.session_state["speaking_submitted"] = True

                    except Exception as e:
                        st.error(f"Something went wrong: {e}")
                        st.stop()

                # Step 4: Extract memories from this attempt
                with st.spinner(
                    "Coach is updating your speaking memory profile..."):
                    try:
                        extract_speaking_memories(
                            learner_id=learner_id,
                            attempt_result=results
                        )

                        # Step 5: Update existing memories
                        scores = results.get("scores", {})
                        update_summary = update_memories(
                            learner_id=learner_id,
                            section="Speaking",
                            score_result={
                                "scores": {
                                    "fluency_coherence": scores.get(
                                        "fluency_coherence", 0
                                    ),
                                    "lexical_resource": scores.get(
                                        "lexical_resource", 0
                                    ),
                                    "grammatical_range": scores.get(
                                        "grammatical_range", 0
                                    ),
                                    "pronunciation_clarity": scores.get(
                                        "pronunciation_clarity", 0
                                    ),
                                },
                                "strengths": scores.get("strengths", []),
                                "weaknesses": scores.get("weaknesses", []),
                                "overall_feedback": results.get(
                                    "feedback_text", ""
                                )
                            }
                        )

                        archived = update_summary.get("archived", 0)
                        if archived > 0:
                            st.success(
                                f"🎉 Great progress! {archived} speaking "
                                f"skill(s) archived as mastered."
                            )

                    except Exception as e:
                        st.warning(
                            f"Results saved but memory update had "
                            f"an issue: {e}"
                        )

                st.rerun()
