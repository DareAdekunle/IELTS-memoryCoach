import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Local dev:    sqlite:///./ielts_coach.db  (default)
# Docker dev:   sqlite:////app/data/db/ielts_coach.db  (set via env)
# Production:   postgresql://ielts:<password>@postgres:5432/ielts_coach
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ielts_coach.db")

# SQLite needs check_same_thread=False; PostgreSQL does not.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
