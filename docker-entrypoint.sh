#!/bin/bash
set -e

echo "Starting IELTS MemoryCoach..."

# Start Nginx in background
echo "Starting Nginx..."
nginx -g "daemon off;" &
NGINX_PID=$!

# Start FastAPI
echo "Starting FastAPI..."
cd /app
uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info &
UVICORN_PID=$!

echo "IELTS MemoryCoach is running"
echo "  Nginx PID: $NGINX_PID"
echo "  FastAPI PID: $UVICORN_PID"

# Wait for either process to exit
wait -n $NGINX_PID $UVICORN_PID
EXIT_CODE=$?

echo "A process exited with code $EXIT_CODE — shutting down"
kill $NGINX_PID $UVICORN_PID 2>/dev/null
exit $EXIT_CODE
