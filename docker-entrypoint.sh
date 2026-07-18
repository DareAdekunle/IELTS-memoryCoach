#!/bin/bash
set -e

echo "Starting Qonda IELTS..."

# ── Wait for PostgreSQL to be ready ──────────────────────────────────────────
if echo "${DATABASE_URL:-}" | grep -q "postgresql"; then
    echo "Waiting for PostgreSQL..."
    python - <<'EOF'
import os, sys, time
try:
    import psycopg2
    url = os.environ["DATABASE_URL"]
    for attempt in range(30):
        try:
            conn = psycopg2.connect(url)
            conn.close()
            print("PostgreSQL is ready.")
            sys.exit(0)
        except psycopg2.OperationalError as e:
            print(f"  Attempt {attempt + 1}/30: {e}")
            time.sleep(2)
    print("PostgreSQL not ready after 60 s — aborting.")
    sys.exit(1)
except ImportError:
    print("psycopg2 not installed — skipping wait.")
EOF
fi

# ── OSS backup: runs only for SQLite deployments (legacy) ────────────────────
if echo "${DATABASE_URL:-sqlite}" | grep -q "sqlite"; then
    DB_URL="${DATABASE_URL:-sqlite:///./ielts_coach.db}"
    DB_FILE="${DB_URL#sqlite:///}"
    mkdir -p "$(dirname "$DB_FILE")"

    if [ ! -f "$DB_FILE" ]; then
        echo "No local database found. Attempting restore from OSS..."
        python scripts/db_backup.py restore || echo "No OSS backup — starting fresh."
    fi

    # Periodic backup loop (every 6 h)
    (
        while true; do
            sleep 21600
            echo "[backup] Running scheduled OSS backup..."
            python scripts/db_backup.py backup || echo "[backup] Failed — continuing."
        done
    ) &
fi

# ── Start Nginx ───────────────────────────────────────────────────────────────
echo "Starting Nginx..."
nginx -g "daemon off;" &
NGINX_PID=$!

# ── Start FastAPI ─────────────────────────────────────────────────────────────
echo "Starting FastAPI..."
uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info &
UVICORN_PID=$!

echo "Qonda IELTS is running"
echo "  Nginx PID:   $NGINX_PID"
echo "  FastAPI PID: $UVICORN_PID"

# ── Wait for either process to exit ──────────────────────────────────────────
wait -n $NGINX_PID $UVICORN_PID
EXIT_CODE=$?

echo "A process exited (code $EXIT_CODE) — shutting down."
kill $NGINX_PID $UVICORN_PID 2>/dev/null || true
exit $EXIT_CODE
