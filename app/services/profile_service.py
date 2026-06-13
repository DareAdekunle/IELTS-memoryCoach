import uuid
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Learner


def create_learner(name: str, target_score: float, test_date: str, current_focus: str) -> str:
    """
    Creates a new learner profile in the database.
    Returns the new learner_id so the app can remember it.

    We generate a unique ID using uuid4 — this ensures no two
    learners ever have the same ID, even if they have the same name.
    """
    db: Session = SessionLocal()

    try:
        learner_id = str(uuid.uuid4())[:8]  # short unique ID e.g. "a3f9b2c1"

        new_learner = Learner(
            learner_id=learner_id,
            name=name,
            target_score=target_score,
            test_date=str(test_date),
            current_focus=current_focus
        )

        db.add(new_learner)
        db.commit()
        db.refresh(new_learner)

        return learner_id

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()


def get_learner(learner_id: str) -> dict | None:
    """
    Fetches a learner profile from the database by their ID.
    Returns a dictionary of their details, or None if not found.
    """
    db: Session = SessionLocal()

    try:
        learner = db.query(Learner).filter(Learner.learner_id == learner_id).first()

        if learner is None:
            return None

        return {
            "learner_id": learner.learner_id,
            "name": learner.name,
            "target_score": learner.target_score,
            "test_date": learner.test_date,
            "current_focus": learner.current_focus,
            "created_at": str(learner.created_at)
        }

    finally:
        db.close()


def get_all_learners() -> list:
    """
    Returns a list of all learners in the database.
    Useful for a profile selector on the home page.
    """
    db: Session = SessionLocal()

    try:
        learners = db.query(Learner).all()
        return [
            {
                "learner_id": l.learner_id,
                "name": l.name,
                "target_score": l.target_score,
                "current_focus": l.current_focus
            }
            for l in learners
        ]

    finally:
        db.close()

