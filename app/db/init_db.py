import sys
import os

# This makes sure Python can find your app/ folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.database import engine, Base
from app.db.models import (
    Learner,
    PracticeAttempt,
    LearnerMemory,
    MasteryScore,
    SessionSummary
)


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done! Tables created:")
    print("  ✅ learners")
    print("  ✅ practice_attempts")
    print("  ✅ learner_memories")
    print("  ✅ mastery_scores")
    print("  ✅ session_summaries")


if __name__ == "__main__":
    init_db()
