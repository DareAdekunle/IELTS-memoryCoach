from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# This is the path to your SQLite file
# It will be created automatically when you first run init_db.py
DATABASE_URL = "sqlite:///./ielts_coach.db"

# The engine is the actual connection to the database
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # needed for SQLite
)

# A session is how you send commands to the database
# Think of it like opening a conversation with the DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent class all your table models will inherit from
Base = declarative_base()


def get_db():
    """
    Opens a database session, gives it to whoever needs it,
    then closes it cleanly when done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
