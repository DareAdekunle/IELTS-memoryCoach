"""
scripts/db_backup.py — SQLite ↔ Alibaba Cloud OSS backup/restore

Usage:
    python scripts/db_backup.py backup   # upload DB snapshot to OSS
    python scripts/db_backup.py restore  # download latest snapshot from OSS

The script reads these env vars (all set in .env):
    DATABASE_URL         — sqlite:////app/data/db/ielts_coach.db
    OSS_ACCESS_KEY_ID
    OSS_ACCESS_KEY_SECRET
    OSS_BUCKET           — ielts-memorycoach-audio
    OSS_ENDPOINT         — oss-ap-southeast-1.aliyuncs.com

The remote key is always  db_backups/ielts_coach.db  (one rolling snapshot).
For point-in-time copies add --timestamp: db_backups/ielts_coach_<ts>.db
"""

import os
import sys
import shutil
import tempfile
from datetime import datetime, timezone

try:
    import oss2
except ImportError:
    print("oss2 not installed — skipping OSS backup", flush=True)
    sys.exit(0)


def _db_path() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./ielts_coach.db")
    # Strip leading sqlite:/// (three slashes = relative, four = absolute)
    path = url.replace("sqlite:///", "", 1)
    return os.path.abspath(path)


def _bucket():
    access_key_id     = os.getenv("OSS_ACCESS_KEY_ID", "")
    access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "")
    endpoint          = os.getenv("OSS_ENDPOINT", "oss-ap-southeast-1.aliyuncs.com")
    bucket_name       = os.getenv("OSS_BUCKET", "ielts-memorycoach-audio")

    if not access_key_id or not access_key_secret:
        print("OSS credentials not set — skipping backup", flush=True)
        sys.exit(0)

    auth = oss2.Auth(access_key_id, access_key_secret)
    return oss2.Bucket(auth, f"https://{endpoint}", bucket_name)


ROLLING_KEY    = "db_backups/ielts_coach.db"
TIMESTAMP_KEY  = lambda ts: f"db_backups/ielts_coach_{ts}.db"


def backup(with_timestamp: bool = False):
    db_file = _db_path()
    if not os.path.exists(db_file):
        print(f"DB not found at {db_file} — nothing to back up", flush=True)
        return

    bucket = _bucket()

    # Copy to a temp file so we don't lock the live DB during upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = tmp.name

    try:
        shutil.copy2(db_file, tmp_path)

        bucket.put_object_from_file(ROLLING_KEY, tmp_path)
        print(f"Backup uploaded → oss://{os.getenv('OSS_BUCKET')}/{ROLLING_KEY}", flush=True)

        if with_timestamp:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            key = TIMESTAMP_KEY(ts)
            bucket.put_object_from_file(key, tmp_path)
            print(f"Timestamped copy → oss://{os.getenv('OSS_BUCKET')}/{key}", flush=True)

    finally:
        os.unlink(tmp_path)


def restore():
    db_file = _db_path()
    db_dir  = os.path.dirname(db_file)

    bucket = _bucket()

    try:
        bucket.head_object(ROLLING_KEY)
    except oss2.exceptions.NoSuchKey:
        print("No backup found on OSS — starting with a fresh database", flush=True)
        return

    os.makedirs(db_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = tmp.name

    try:
        bucket.get_object_to_file(ROLLING_KEY, tmp_path)
        shutil.move(tmp_path, db_file)
        print(f"Database restored from oss://{os.getenv('OSS_BUCKET')}/{ROLLING_KEY}", flush=True)
    except Exception as e:
        os.unlink(tmp_path)
        print(f"Restore failed: {e}", flush=True)
        raise


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "backup"
    timestamp = "--timestamp" in sys.argv

    if cmd == "backup":
        backup(with_timestamp=timestamp)
    elif cmd == "restore":
        restore()
    else:
        print(f"Unknown command: {cmd}. Use 'backup' or 'restore'.", flush=True)
        sys.exit(1)
