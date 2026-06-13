import streamlit as st
import sys
import os

# This tells Python where to find your app/ folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.profile_service import create_learner, get_learner, get_all_learners

st.set_page_config(
    page_title="Learner Profile",
    page_icon="🙋",
    layout="wide"
)

st.title("🙋 Learner Profile")
st.markdown("Create your profile so your coach can personalise your sessions.")
st.markdown("---")

# Initialise session state variables if they don't exist yet
if "learner_id" not in st.session_state:
    st.session_state["learner_id"] = None
if "learner_name" not in st.session_state:
    st.session_state["learner_name"] = None


# ─── CASE 1: Learner already has an active session ───────────────────────────
if st.session_state["learner_id"] is not None:

    learner = get_learner(st.session_state["learner_id"])

    if learner:
        st.success(f"Welcome back, **{learner['name']}**! 👋")
        st.markdown("---")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Target Score", learner["target_score"])
        with col2:
            st.metric("Current Focus", learner["current_focus"])
        with col3:
            st.metric("Test Date", learner["test_date"])

        st.markdown(f"**Learner ID:** `{learner['learner_id']}`")
        st.markdown("---")

        if st.button("Switch to a different profile"):
            st.session_state["learner_id"] = None
            st.session_state["learner_name"] = None
            st.rerun()


# ─── CASE 2: No active session — show new or returning options ────────────────
else:
    tab1, tab2 = st.tabs(["✨ New Learner", "👋 Returning Learner"])

    # New learner form
    with tab1:
        st.subheader("Create your profile")

        with st.form("profile_form"):
            name = st.text_input(
                "Your name",
                placeholder="e.g. Amina"
            )
            target_score = st.number_input(
                "Target IELTS score",
                min_value=0.0,
                max_value=9.0,
                value=7.0,
                step=0.5,
                help="IELTS scores range from 0 to 9"
            )
            test_date = st.date_input(
                "Your target test date",
                help="When are you planning to take the exam?"
            )
            current_focus = st.selectbox(
                "What do you want to focus on first?",
                ["Writing", "Reading", "Speaking", "Listening"]
            )

            submitted = st.form_submit_button("Create Profile")

            if submitted:
                if not name.strip():
                    st.error("Please enter your name.")
                else:
                    # Call the profile service to save to database
                    learner_id = create_learner(
                        name=name.strip(),
                        target_score=target_score,
                        test_date=str(test_date),
                        current_focus=current_focus
                    )

                    # Save to session state so other pages can access it
                    st.session_state["learner_id"] = learner_id
                    st.session_state["learner_name"] = name.strip()

                    st.success(f"Profile created! Welcome, {name} 🎉")
                    st.rerun()

    # Returning learner selector
    with tab2:
        st.subheader("Select your existing profile")

        all_learners = get_all_learners()

        if not all_learners:
            st.info("No profiles found yet. Create a new profile in the first tab.")
        else:
            # Build a dropdown of existing learners
            learner_options = {
                f"{l['name']} (ID: {l['learner_id']})": l["learner_id"]
                for l in all_learners
            }

            selected = st.selectbox(
                "Choose your profile",
                options=list(learner_options.keys())
            )

            if st.button("Load Profile"):
                selected_id = learner_options[selected]
                learner = get_learner(selected_id)

                if learner:
                    st.session_state["learner_id"] = learner["learner_id"]
                    st.session_state["learner_name"] = learner["name"]
                    st.success(f"Welcome back, {learner['name']}!")
                    st.rerun()

