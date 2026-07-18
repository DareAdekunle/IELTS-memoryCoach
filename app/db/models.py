from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.database import Base


class Learner(Base):
    """
    Stores basic identity and goal info for each learner.
    One row per learner.
    """
    __tablename__ = "learners"

    learner_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    target_score = Column(Float, nullable=True)
    test_date = Column(String, nullable=True)
    current_focus = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class PracticeAttempt(Base):
    """
    Stores every essay or answer a learner submits.
    One row per attempt.
    """
    __tablename__ = "practice_attempts"

    attempt_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False)
    section = Column(String, nullable=False)        # e.g. "Writing"
    task_type = Column(String, nullable=True)        # e.g. "Academic Discussion"
    prompt = Column(Text, nullable=False)            # the question given
    learner_response = Column(Text, nullable=False)  # what the learner wrote
    score_json = Column(Text, nullable=True)         # Qwen's scores as JSON string
    feedback = Column(Text, nullable=True)           # Qwen's feedback text
    created_at = Column(DateTime, default=func.now())


class LearnerMemory(Base):
    """
    Stores what the coach has learned about the learner over time.
    This is the heart of the MemoryAgent.
    One row per memory. Memories can be updated or archived.
    """
    __tablename__ = "learner_memories"

    memory_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False)
    section = Column(String, nullable=False)         # e.g. "Writing"
    skill = Column(String, nullable=False)           # e.g. "Thesis clarity"
    memory_type = Column(String, nullable=False)     # "weakness", "strength", "preference"
    memory_text = Column(Text, nullable=False)       # the actual memory sentence
    confidence = Column(Float, default=0.5)          # 0.0 to 1.0
    evidence_count = Column(Integer, default=1)      # how many attempts back this up
    status = Column(String, default="active")        # "active" or "archived"
    embedding = Column(Text, nullable=True)          # JSON-serialised float list (text-embedding-v3)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class StudySchedule(Base):
    """
    Stores a learner's recurring study schedule.
    One active row per learner. Google Calendar integration is optional.
    """
    __tablename__ = "study_schedules"

    schedule_id      = Column(String, primary_key=True, index=True)
    learner_id       = Column(String, nullable=False, index=True)
    days_of_week     = Column(Text, nullable=False)   # JSON: ["Mon","Wed","Fri"]
    study_time       = Column(String(5), nullable=False)  # "07:00"
    duration_minutes = Column(Integer, nullable=False, default=30)
    timezone         = Column(String(60), nullable=False, default="UTC")
    # Google Calendar (all nullable — calendar connection is optional)
    google_refresh_token     = Column(Text, nullable=True)
    google_calendar_event_id = Column(Text, nullable=True)  # recurring series ID
    google_email             = Column(String, nullable=True)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, default=func.now())
    updated_at       = Column(DateTime, default=func.now(), onupdate=func.now())


class MasteryScore(Base):
    """
    Tracks the learner's current level per skill.
    Updated after each attempt.
    """
    __tablename__ = "mastery_scores"

    mastery_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False)
    section = Column(String, nullable=False)         # e.g. "Writing"
    skill = Column(String, nullable=False)           # e.g. "Grammar"
    score = Column(Float, default=0.0)               # 0.0 to 5.0
    status = Column(String, default="active")
    last_updated = Column(DateTime, default=func.now())


class SessionSummary(Base):
    """
    Stores a summary of each coaching session.
    Useful for the progress dashboard.
    """
    __tablename__ = "session_summaries"

    session_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False)
    section = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class LearnerSkillRank(Base):
    """
    Tracks a learner's mastery progress on one granular skill
    within one section (currently Writing only).

    Rank moves up via clean_streak — 3 consecutive attempts where
    Qwen classifies this skill as "demonstrated_strength" with no
    weakness in between. Any "demonstrated_weakness" resets the
    streak to 0. There is no automatic rank-down.

    One row per (learner_id, section, skill_id).
    """
    __tablename__ = "learner_skill_ranks"

    rank_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False)
    section = Column(String, nullable=False)       # "Writing" for now
    skill_id = Column(String, nullable=False)       # e.g. "tr_conclusion_synthesis"
    current_rank = Column(Integer, default=1)       # 1 (beginner) to 5 (advanced)
    clean_streak = Column(Integer, default=0)        # consecutive clean attempts
    total_evidence = Column(Integer, default=0)       # total times this skill was assessed
    last_classification = Column(String, nullable=True)  # last result: weakness/strength/not_applicable
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class TutorSession(Base):
    """
    One row per Tutor chat session. Anchors the pedagogical session
    plan and all evidence events recorded during the session.

    Conversation history stays client-side (unchanged) — this row is
    the server-side identity of the session, not a transcript.
    """
    __tablename__ = "tutor_sessions"

    session_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False)
    state = Column(String, default="introduction")   # last known conversation state
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)   # set at bridge_to_practice


class LearnerCriterionState(Base):
    """
    Pedagogy-specific state per (learner, section, criterion).

    IMPORTANT: band and stage are NEVER stored here — they are always
    derived live from learner_skill_ranks via stage_resolver so there
    is a single source of truth. This table holds only what cannot be
    derived: the Coach-managed support level and evidence counters.

    One row per (learner_id, section, criterion_id).
    """
    __tablename__ = "learner_criterion_state"

    state_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False)
    criterion_id = Column(String, nullable=False)     # taxonomy category_id
    support_level = Column(String, nullable=True)     # full/partial/minimal/none — None = use stage default
    hint_dependency_score = Column(Float, default=0.0)  # rolling avg hint level
    independent_success_count = Column(Integer, default=0)
    timed_success_count = Column(Integer, default=0)
    last_support_change = Column(String, nullable=True)  # "reduced" / "restored"
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class TutorSessionPlan(Base):
    """
    The Pedagogy Planner's structured teaching plan for one Tutor
    session. Created deterministically at session start; the LLM
    carries out the plan, it does not define it.
    """
    __tablename__ = "tutor_session_plans"

    session_plan_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    learner_id = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False)
    target_skill = Column(String, nullable=False)      # taxonomy skill_id
    target_criterion = Column(String, nullable=False)  # taxonomy category_id
    target_descriptor = Column(Text, nullable=True)
    current_stage = Column(String, nullable=False)
    dominant_framework = Column(String, nullable=False)
    supporting_frameworks_json = Column(Text, nullable=True)
    support_level = Column(String, nullable=False)
    practice_conditions_json = Column(Text, nullable=True)
    feedback_priorities_json = Column(Text, nullable=True)
    exit_criteria_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    outcome = Column(String, nullable=True)  # completed / needs_more_guided_practice / ...


class PedagogicalEvent(Base):
    """
    Raw evidence of what happened during a Tutor session.
    The Tutor records what happened; the Coach decides what it means.
    """
    __tablename__ = "pedagogical_events"

    event_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    learner_id = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False)
    criterion_id = Column(String, nullable=True)
    framework_id = Column(String, nullable=True)
    action_type = Column(String, nullable=False)
    # framework_started / model_shown / learner_attempted / feedback_given /
    # hint_given / self_correction_succeeded / self_correction_failed /
    # independent_check_started / exit_criteria_met / framework_completed
    success = Column(Integer, nullable=True)   # 1 / 0 / NULL(not applicable)
    evidence_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class HintEvent(Base):
    """
    Every hint the Tutor gives, with its ladder level.
    Falling hint-dependence over time is promotion evidence.
    """
    __tablename__ = "hint_events"

    hint_event_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    learner_id = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False)
    criterion_id = Column(String, nullable=True)
    framework_id = Column(String, nullable=True)
    hint_level = Column(Integer, nullable=False)   # 1 (weakest) .. 4 (full answer)
    self_corrected = Column(Integer, nullable=True)  # 1 / 0 / NULL(unknown yet)
    created_at = Column(DateTime, default=func.now())


class LearnerSeenContent(Base):
    """
    Tracks which content items a learner has already seen.
    Used to ensure adaptive selection avoids serving the same
    passage, prompt or track twice — cycling back only when
    all items at the current difficulty level have been seen.

    One row per (learner_id, section, content_id).
    """
    __tablename__ = "learner_seen_content"

    seen_id = Column(String, primary_key=True, index=True)
    learner_id = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False)      # Writing / Reading / Speaking / Listening
    content_id = Column(String, nullable=False)   # passage_id / prompt_id / track_id
    seen_at = Column(DateTime, default=func.now())
