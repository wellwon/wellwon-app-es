#!/bin/bash
# Start all WellWon services with single-instance guarantee

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${PROJECT_ROOT}/.pids"
LOG_DIR="${PROJECT_ROOT}/logs"

# Create directories
mkdir -p "$PID_DIR" "$LOG_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if process is running
is_running() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Running
        else
            rm -f "$pid_file"  # Stale PID file
            return 1  # Not running
        fi
    fi
    return 1  # PID file doesn't exist
}

# Function to kill process by PID file
kill_process() {
    local pid_file="$1"
    local name="$2"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}Killing existing $name (PID: $pid)...${NC}"
            kill -9 "$pid" 2>/dev/null || true
            sleep 1
        fi
        rm -f "$pid_file"
    fi
}

# Function to start server
start_server() {
    local pid_file="${PID_DIR}/server.pid"

    if is_running "$pid_file"; then
        echo -e "${GREEN}Server already running (PID: $(cat $pid_file))${NC}"
        return 0
    fi

    # Kill any processes on port 5002
    PIDS=$(lsof -ti :5002 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}Killing processes on port 5002: $PIDS${NC}"
        kill -9 $PIDS 2>/dev/null || true
        sleep 1
    fi

    echo -e "${GREEN}Starting WellWon server with Granian...${NC}"
    cd "$PROJECT_ROOT"

    # Determine environment (dev/prod)
    ENV="${ENVIRONMENT:-development}"

    if [ "$ENV" = "production" ]; then
        echo -e "${GREEN}Mode: PRODUCTION (workers=4, no reload)${NC}"
        nohup granian --interface asgi app.server:app \
            --host 0.0.0.0 \
            --port 5002 \
            --workers 4 \
            --http 2 \
            > "${LOG_DIR}/server.log" 2>&1 &
    else
        echo -e "${GREEN}Mode: DEVELOPMENT (reload enabled)${NC}"
        nohup granian --interface asgi app.server:app \
            --host 0.0.0.0 \
            --port 5002 \
            --reload \
            --http 1 \
            > "${LOG_DIR}/server.log" 2>&1 &
    fi

    echo $! > "$pid_file"
    echo -e "${GREEN}Server started (PID: $(cat $pid_file))${NC}"
}

# Function to start worker
start_worker() {
    local worker_name="$1"
    local worker_module="$2"
    local pid_file="${PID_DIR}/${worker_name}.pid"

    if is_running "$pid_file"; then
        echo -e "${GREEN}${worker_name} already running (PID: $(cat $pid_file))${NC}"
        return 0
    fi

    # Kill any existing instances of this worker (only WellWon - check working directory, macOS compatible)
    for pid in $(pgrep -f "$worker_module" 2>/dev/null); do
        cwd=$(lsof -p "$pid" 2>/dev/null | grep cwd | awk '{print $NF}')
        if [[ "$cwd" == *"WellWon"* ]]; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    sleep 1

    echo -e "${GREEN}Starting ${worker_name}...${NC}"
    cd "$PROJECT_ROOT"
    nohup python -m "$worker_module" > "${LOG_DIR}/${worker_name}.log" 2>&1 &
    echo $! > "$pid_file"
    echo -e "${GREEN}${worker_name} started (PID: $(cat $pid_file))${NC}"
}

# Main execution
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  TradeCore Process Manager${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Start server
start_server

echo ""
echo -e "${YELLOW}Workers should be started separately in production.${NC}"
echo -e "${YELLOW}To start workers, use:${NC}"
echo -e "  ${GREEN}./scripts/start_all.sh --with-workers${NC}"
echo ""

# Check if --with-workers flag is provided
if [[ "$1" == "--with-workers" ]]; then
    echo -e "${GREEN}Starting workers...${NC}"
    start_worker "event_processor" "app.workers.event_processor_worker"
    start_worker "data_sync" "app.workers.data_sync_worker"
    echo ""
fi

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Status${NC}"
echo -e "${GREEN}======================================${NC}"

# Show status
for pid_file in "${PID_DIR}"/*.pid; do
    if [ -f "$pid_file" ]; then
        name=$(basename "$pid_file" .pid)
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $name (PID: $pid)${NC}"
        else
            echo -e "${RED}✗ $name (stale PID: $pid)${NC}"
            rm -f "$pid_file"
        fi
    fi
done

echo ""
echo -e "${GREEN}Logs: ${LOG_DIR}${NC}"
echo -e "${GREEN}PIDs: ${PID_DIR}${NC}"
echo ""
echo -e "${YELLOW}To stop all services: ./scripts/stop_all.sh${NC}"
