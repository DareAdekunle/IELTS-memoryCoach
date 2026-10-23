"""
Bring the database schema up to date. Run before the API starts.

    python scripts/migrate.py

- Fresh database        → alembic upgrade head
- Alembic-managed DB    → alembic upgrade head
- Pre-Alembic DB (tables exist, no alembic_version) → create any missing
  tables and legacy columns, stamp the baseline, then upgrade head.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db.database import Base, engine
import app.db.models  # noqa: F401
import api.auth.models  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Columns older databases may lack; previously added at API startup.
LEGACY_COLUMNS = [
    ("learner_memories", "embedding", "TEXT"),
    ("users", "whatsapp_number", "VARCHAR"),
    ("users", "telegram_chat_id", "VARCHAR"),
]


def _adopt_legacy_database(cfg: Config) -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        insp = inspect(conn)
        for table, column, sql_type in LEGACY_COLUMNS:
            if column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
    baseline = ScriptDirectory.from_config(cfg).get_base()
    command.stamp(cfg, baseline)
    print(f"[migrate] Adopted existing database at baseline {baseline}")


def main() -> None:
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "migrations"))

    tables = set(inspect(engine).get_table_names())
    if tables and "alembic_version" not in tables:
        _adopt_legacy_database(cfg)

    command.upgrade(cfg, "head")
    print("[migrate] Schema is up to date")


if __name__ == "__main__":
    main()
