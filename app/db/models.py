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
