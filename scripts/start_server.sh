#!/bin/bash
# Start WellWon server with automatic cleanup of existing instances

set -e

PORT=5002
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Checking for existing processes on port ${PORT}..."

# Kill any processes listening on the port
PIDS=$(lsof -ti :${PORT} 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo "Found processes on port ${PORT}: $PIDS"
    echo "Killing existing processes..."
    kill -9 $PIDS
    sleep 2
fi

# Also kill any server or worker processes by name (only WellWon - check working directory)
echo "Checking for orphaned WellWon workers..."

# Kill processes from WellWon directory only (macOS compatible)
for pattern in "granian" "event_processor_worker" "data_sync_worker"; do
    for pid in $(pgrep -f "$pattern" 2>/dev/null); do
        cwd=$(lsof -p "$pid" 2>/dev/null | grep cwd | awk '{print $NF}')
        if [[ "$cwd" == *"WellWon"* ]]; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
done

sleep 1

echo "Starting WellWon server on port ${PORT} with Granian..."
cd "$PROJECT_ROOT"

# Determine environment (dev/prod)
ENV="${ENVIRONMENT:-development}"

if [ "$ENV" = "production" ]; then
    echo "Mode: PRODUCTION (workers=4, no reload)"
    exec granian --interface asgi app.server:app \
        --host 0.0.0.0 \
        --port ${PORT} \
        --workers 4 \
        --http 2 \
        --log-level info
else
    echo "Mode: DEVELOPMENT (reload enabled)"
    exec granian --interface asgi app.server:app \
        --host 0.0.0.0 \
        --port ${PORT} \
        --reload \
        --http 1 \
        --log-level info
fi
