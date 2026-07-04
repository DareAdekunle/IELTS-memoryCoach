import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.practice_service import get_random_writing_prompt
from app.services.skill_classifier_service import classify_writing_skills
from app.services.memory_service import apply_skill_classifications_batch
from app.services.scoring_service import evaluate_writing
from app.services.memory_service import (
    save_attempt,
    extract_and_save_memories,
    get_relevant_memories,
    update_memories
)

st.set_page_config(
    page_title="Writing Coach",
    page_icon="✍️",
    layout="wide"
)

st.title("✍️ Writing Coach")
st.markdown("Practice your IELTS writing and receive personalised AI feedback.")
st.markdown("---")

# Always check for a profile first
if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
    st.warning("👈 Please create your **Learner Profile** first before starting practice.")
    st.stop()

learner_id = st.session_state["learner_id"]

# ─── Memory panel ─────────────────────────────────────────────────────────────
# Retrieve and show existing memories before the learner starts
memories = get_relevant_memories(learner_id, section="Writing", limit=3)

if memories:
    with st.expander("🧠 What your coach remembers about you", expanded=True):
        for mem in memories:
            icon = "⚠️" if mem["memory_type"] == "weakness" else "✅"
            st.markdown(f"{icon} **{mem['skill']}:** {mem['memory_text']}")

# ─── Prompt display ───────────────────────────────────────────────────────────
if "current_prompt" not in st.session_state:
    st.session_state["current_prompt"] = get_random_writing_prompt()

prompt = st.session_state["current_prompt"]

st.subheader("📋 Today's Writing Prompt")

col1, col2 = st.columns([3, 1])
with col1:
    st.info(f"**Task Type:** {prompt['task_type']}\n\n{prompt['prompt']}")
with col2:
    st.markdown("**Target Skills**")
    for skill in prompt["target_skills"]:
        st.markdown(f"- {skill.replace('_', ' ').title()}")
    st.markdown(f"**Difficulty:** {prompt['difficulty'].title()}")

if st.button("🔄 Get a Different Prompt"):
    del st.session_state["current_prompt"]
    if "last_feedback" in st.session_state:
        del st.session_state["last_feedback"]
    st.rerun()

# ─── Response area ────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("✍️ Your Response")

response = st.text_area(
    "Write your essay here",
    height=350,
    placeholder="Start writing your essay here. Aim for at least 250 words."
)

word_count = len(response.split()) if response.strip() else 0

if word_count == 0:
    st.caption("Word count: 0 / 250 minimum")
elif word_count < 250:
    st.warning(f"⚠️ Word count: {word_count} / 250 — you need {250 - word_count} more words")
else:
    st.success(f"✅ Word count: {word_count} — good to submit!")

submitted = st.button("Submit for Feedback ✅", disabled=word_count < 50)

# ─── Scoring + Saving + Memory Extraction ────────────────────────────────────
if submitted:
    with st.spinner("Your coach is reading your essay and your history..."):
        try:
            # Step 1: Score the essay — now passing memories as context
            result = evaluate_writing(
                prompt=prompt["prompt"],
                essay=response,
                memories=memories
            )
            st.session_state["last_feedback"] = result

            # Step 2: Save the attempt
            save_attempt(
                learner_id=learner_id,
                section="Writing",
                task_type=prompt["task_type"],
                prompt=prompt["prompt"],
                learner_response=response,
                score_json=result,
                feedback=result.get("overall_feedback", "")
            )

        except Exception as e:
            st.error(f"Something went wrong during scoring: {e}")
            st.stop()

    # Step 3: Extract and update memories
    # Only runs if scoring succeeded (st.stop() prevents reaching here on failure)
    if "last_feedback" in st.session_state:
        result = st.session_state["last_feedback"]
        with st.spinner("Coach is updating your memory profile..."):
            try:
                extract_and_save_memories(
                    learner_id=learner_id,
                    section="Writing",
                    prompt=prompt["prompt"],
                    score_result=result
                )

                update_summary = update_memories(
                    learner_id=learner_id,
                    section="Writing",
                    score_result=result
                )

                archived = update_summary.get("archived", 0)
                strengthened = update_summary.get("strengthened", 0)

                if archived > 0:
                    st.success(
                        f"🎉 Great progress! {archived} weakness(es) have been "
                        f"archived — your coach considers these mastered."
                    )
                if strengthened > 0:
                    st.info(
                        f"🧠 {strengthened} pattern(s) have been reinforced "
                        f"in your memory profile."
                    )

                # Phase D — Skill taxonomy classification and ranking
                # This is a SEPARATE Qwen call (Phase C design) that maps
                # this essay against the fixed 13-skill taxonomy and updates
                # learner_skill_ranks via the deterministic rule engine.
                classifications = classify_writing_skills(
                    prompt=prompt["prompt"],
                    essay=response
                )

                rank_results = apply_skill_classifications_batch(
                    learner_id=learner_id,
                    section="Writing",
                    classifications=classifications
                )

                ranked_up_skills = [
                    r for r in rank_results if r["ranked_up"]
                ]

                if ranked_up_skills:
                    from app.services.skill_taxonomy_service import (
                        get_skill_by_id,
                        get_rank_name
                    )
                    for r in ranked_up_skills:
                        skill_info = get_skill_by_id(r["skill_id"])
                        new_rank_name = get_rank_name(r["current_rank"])
                        st.success(
                            f"🎯 Skill level up! "
                            f"**{skill_info['skill_name']}** is now "
                            f"**{new_rank_name}** "
                            f"(rank {r['current_rank']}/5)"
                        )

            except Exception as e:
                st.warning(f"Feedback saved but memory update had an issue: {e}")

# ─── Feedback display ─────────────────────────────────────────────────────────
if "last_feedback" in st.session_state:
    result = st.session_state["last_feedback"]

    st.markdown("---")
    st.subheader("📊 Your Feedback")

    st.info(f"💬 **Overall:** {result['overall_feedback']}")

    st.markdown("#### Skill Scores")
    scores = result["scores"]
    cols = st.columns(5)
    skill_labels = {
        "thesis_clarity": "Thesis Clarity",
        "organization": "Organization",
        "grammar": "Grammar",
        "vocabulary": "Vocabulary",
        "idea_development": "Idea Development"
    }
    for i, (skill_key, label) in enumerate(skill_labels.items()):
        with cols[i]:
            score = scores.get(skill_key, 0)
            st.metric(label=label, value=f"{score} / 5")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### ✅ Strengths")
        for s in result.get("strengths", []):
            st.markdown(f"- {s}")

    with col2:
        st.markdown("#### ⚠️ Areas to Improve")
        for w in result.get("weaknesses", []):
            st.markdown(f"- {w}")

    st.markdown("---")
    st.success(f"🎯 **Recommended Next Step:** {result['recommended_next_step']}")
