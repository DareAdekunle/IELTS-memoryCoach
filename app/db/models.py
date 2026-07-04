from sqlalchemy import Column, String, Integer, Float, Text, DateTime
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
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


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
