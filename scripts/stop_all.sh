#!/bin/bash
# Stop all WellWon processes

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${PROJECT_ROOT}/.pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping all WellWon processes...${NC}"
echo ""

# Function to kill WellWon processes
kill_wellwon_processes() {
    local pattern="$1"
    local name="$2"
    local killed=0

    for pid in $(pgrep -f "$pattern" 2>/dev/null); do
        # Get working directory (macOS compatible)
        local cwd=$(lsof -p "$pid" 2>/dev/null | grep cwd | awk '{print $NF}')
        if [[ "$cwd" == *"WellWon"* ]]; then
            echo -e "${YELLOW}Killing $name (PID: $pid)${NC}"
            kill -9 "$pid" 2>/dev/null && killed=1
        fi
    done

    [ $killed -eq 1 ] && echo -e "${GREEN}Stopped $name${NC}" || echo -e "${GREEN}No $name running${NC}"
}

# Kill all WellWon processes
kill_wellwon_processes "granian" "granian server"
kill_wellwon_processes "event_processor_worker" "event processor worker"
kill_wellwon_processes "data_sync_worker" "data sync worker"

# Kill anything on port 5002
PIDS=$(lsof -ti :5002 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}Killing processes on port 5002: $PIDS${NC}"
    kill -9 $PIDS 2>/dev/null || true
fi

# Clean up PID files
if [ -d "$PID_DIR" ]; then
    rm -rf "$PID_DIR"/*.pid 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}All WellWon processes stopped${NC}"
