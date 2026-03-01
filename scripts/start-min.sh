#!/bin/bash
set -euo pipefail

# Start Minimal Services
# Starts minimal mock services for development

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Audit logging
audit_log() {
    local action="$1"
    local resource="$2"
    local result="$3"
    local hash_value="${4:-}"
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local request_id=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "unknown")
    local correlation_id=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "unknown")
    
    local log_entry=$(cat <<EOF
{
  "timestamp": "${timestamp}",
  "actor": "start-min",
  "action": "${action}",
  "resource": "${resource}",
  "result": "${result}",
  "hash": "${hash_value}",
  "version": "1.0.0",
  "requestId": "${request_id}",
  "correlationId": "${correlation_id}",
  "ip": "unknown",
  "userAgent": "start-min.sh"
}
EOF
)
    
    local audit_dir="${ROOT_DIR}/audit"
    mkdir -p "${audit_dir}"
    local audit_file="${audit_dir}/start-min_$(date -u +"%Y%m%d").jsonl"
    echo "${log_entry}" >> "${audit_file}"
}

echo -e "${GREEN}[start-min] Starting minimal services...${NC}"

# Check if .env exists
if [[ ! -f "${ROOT_DIR}/.env" ]]; then
    echo -e "${YELLOW}[start-min] Warning: .env not found, creating from .env.example${NC}"
    if [[ -f "${ROOT_DIR}/.env.example" ]]; then
        cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
    else
        echo "NODE_ENV=development" > "${ROOT_DIR}/.env"
    fi
    audit_log "setup_env" ".env" "success" ""
fi

# Source environment
set -a
source "${ROOT_DIR}/.env"
set +a

# Create logs directory
mkdir -p "${ROOT_DIR}/logs"

# Start mock services (if any)
echo "[start-min] Checking for mock services..."

# Example: Start a simple HTTP server for testing
if command -v python3 &> /dev/null; then
    echo "[start-min] Starting mock API server on port 8080..."
    nohup python3 -m http.server 8080 > "${ROOT_DIR}/logs/mock-api.log" 2>&1 &
    MOCK_PID=$!
    echo "${MOCK_PID}" > "${ROOT_DIR}/.mock-api.pid"
    echo -e "  ${GREEN}✓${NC} Mock API server started (PID: ${MOCK_PID})"
    audit_log "start_service" "mock-api" "success" ""
fi

# Summary
echo ""
echo -e "${GREEN}[start-min] Minimal services started${NC}"
echo ""
echo "Running services:"
echo "  - Mock API: http://localhost:8080"
echo ""
echo "Logs: ${ROOT_DIR}/logs/"
echo ""
echo "To stop services:"
echo "  kill \$(cat ${ROOT_DIR}/.mock-api.pid)"
echo ""

audit_log "start-min_complete" "services" "success" ""

exit 0