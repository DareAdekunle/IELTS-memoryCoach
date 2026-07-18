"""
scripts/migrate_sqlite_to_postgres.py

One-time migration from the legacy SQLite database to PostgreSQL.

Usage (run from repo root, after the postgres container is healthy):
    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite ./ielts_coach.db \
        --postgres "postgresql://ielts:<password>@localhost:5432/ielts_coach"

What it does:
  1. Reads every row from each table in the SQLite database.
  2. Inserts all rows into the PostgreSQL database.
  3. Skips rows that already exist (idempotent — safe to re-run).

Tables migrated (all of them):
  users, learners, practice_attempts, learner_memories,
  mastery_scores, session_summaries, learner_skill_ranks,
  tutor_sessions, learner_criterion_state, tutor_session_plans,
  pedagogical_events, hint_events, learner_seen_content
"""

import argparse
import sys
from datetime import datetime

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker


def migrate(sqlite_url: str, postgres_url: str) -> None:
    if not sqlite_url.startswith("sqlite"):
        sqlite_url = f"sqlite:///{sqlite_url}"

    print(f"Source:      {sqlite_url}")
    print(f"Destination: {postgres_url}")

    src_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    dst_engine = create_engine(postgres_url)

    # Create all tables in Postgres (SQLAlchemy will no-op if they exist)
    sys.path.insert(0, ".")
    from app.db.database import Base
    import app.db.models  # register all models
    import api.auth.models  # register User model
    Base.metadata.create_all(bind=dst_engine)

    inspector = inspect(src_engine)
    tables = inspector.get_table_names()
    print(f"\nFound {len(tables)} tables in SQLite: {tables}")

    src_conn = src_engine.connect()
    dst_Session = sessionmaker(bind=dst_engine)
    dst_conn = dst_engine.connect()

    total_rows = 0
    total_skipped = 0

    for table in tables:
        rows = src_conn.execute(text(f'SELECT * FROM "{table}"')).fetchall()
        if not rows:
            print(f"  {table}: empty — skipping")
            continue

        cols = src_conn.execute(
            text(f'SELECT * FROM "{table}" LIMIT 0')
        ).keys()
        col_list = list(cols)

        inserted = 0
        skipped = 0

        for row in rows:
            row_dict = dict(zip(col_list, row))
            # Build an INSERT ... ON CONFLICT DO NOTHING
            placeholders = ", ".join(f":{c}" for c in col_list)
            col_names    = ", ".join(f'"{c}"' for c in col_list)
            stmt = text(
                f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'
                f' ON CONFLICT DO NOTHING'
            )
            try:
                with dst_engine.begin() as tx:
                    result = tx.execute(stmt, row_dict)
                    if result.rowcount:
                        inserted += 1
                    else:
                        skipped += 1
            except Exception as e:
                print(f"    ⚠️  Row error in {table}: {e}")
                skipped += 1

        print(f"  {table}: {inserted} inserted, {skipped} skipped")
        total_rows    += inserted
        total_skipped += skipped

    src_conn.close()
    dst_conn.close()

    print(f"\nMigration complete: {total_rows} rows inserted, {total_skipped} skipped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite",   required=True, help="SQLite file path or URL")
    parser.add_argument("--postgres", required=True, help="PostgreSQL connection string")
    args = parser.parse_args()
    migrate(args.sqlite, args.postgres)
