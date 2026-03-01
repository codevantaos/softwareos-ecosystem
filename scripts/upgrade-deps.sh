#!/bin/bash
set -euo pipefail

# Upgrade Dependencies Script
# Upgrades dependencies with snapshot and rollback capability

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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
  "actor": "upgrade-deps",
  "action": "${action}",
  "resource": "${resource}",
  "result": "${result}",
  "hash": "${hash_value}",
  "version": "1.0.0",
  "requestId": "${request_id}",
  "correlationId": "${correlation_id}",
  "ip": "unknown",
  "userAgent": "upgrade-deps.sh"
}
EOF
)
    
    local audit_dir="${ROOT_DIR}/audit"
    mkdir -p "${audit_dir}"
    local audit_file="${audit_dir}/upgrade-deps_$(date -u +"%Y%m%d").jsonl"
    echo "${log_entry}" >> "${audit_file}"
}

SNAPSHOT_DIR="${ROOT_DIR}/.snapshots"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
SNAPSHOT_PATH="${SNAPSHOT_DIR}/upgrade-${TIMESTAMP}"

echo -e "${GREEN}[upgrade-deps] Starting dependency upgrade...${NC}"
echo ""

# Create snapshot directory
mkdir -p "${SNAPSHOT_PATH}"

# Snapshot current state
echo "[upgrade-deps] Creating snapshot of current state..."
SNAPSHOT_FILE="${SNAPSHOT_PATH}/snapshot.json"

cat > "${SNAPSHOT_FILE}" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "action": "pre-upgrade-snapshot",
  "files": []
}
EOF

# Snapshot Python requirements
if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
    cp "${ROOT_DIR}/requirements.txt" "${SNAPSHOT_PATH}/requirements.txt.bak"
    echo "  ✓ requirements.txt"
    audit_log "snapshot" "requirements.txt" "success" ""
fi

# Snapshot package.json
if [[ -f "${ROOT_DIR}/package.json" ]]; then
    cp "${ROOT_DIR}/package.json" "${SNAPSHOT_PATH}/package.json.bak"
    cp "${ROOT_DIR}/package-lock.json" "${SNAPSHOT_PATH}/package-lock.json.bak" 2>/dev/null || true
    echo "  ✓ package.json"
    audit_log "snapshot" "package.json" "success" ""
fi

# Snapshot go.mod
if [[ -f "${ROOT_DIR}/go.mod" ]]; then
    cp "${ROOT_DIR}/go.mod" "${SNAPSHOT_PATH}/go.mod.bak"
    cp "${ROOT_DIR}/go.sum" "${SNAPSHOT_PATH}/go.sum.bak" 2>/dev/null || true
    echo "  ✓ go.mod"
    audit_log "snapshot" "go.mod" "success" ""
fi

echo ""
echo "[upgrade-deps] Upgrading dependencies..."

# Upgrade Python dependencies
if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
    echo "  Upgrading Python packages..."
    if pip3 install --upgrade -r "${ROOT_DIR}/requirements.txt" &> /dev/null; then
        echo -e "    ${GREEN}✓${NC} Python packages upgraded"
        audit_log "upgrade_python" "requirements.txt" "success" ""
    else
        echo -e "    ${YELLOW}✗${NC} Python packages upgrade failed"
        audit_log "upgrade_python" "requirements.txt" "failure" ""
    fi
fi

# Upgrade Node.js dependencies
if [[ -f "${ROOT_DIR}/package.json" ]]; then
    echo "  Upgrading Node.js packages..."
    if npm update &> /dev/null; then
        echo -e "    ${GREEN}✓${NC} Node.js packages upgraded"
        audit_log "upgrade_node" "package.json" "success" ""
    else
        echo -e "    ${YELLOW}✗${NC} Node.js packages upgrade failed"
        audit_log "upgrade_node" "package.json" "failure" ""
    fi
fi

# Upgrade Go dependencies
if [[ -f "${ROOT_DIR}/go.mod" ]]; then
    echo "  Upgrading Go modules..."
    if go get -u ./... && go mod tidy &> /dev/null; then
        echo -e "    ${GREEN}✓${NC} Go modules upgraded"
        audit_log "upgrade_go" "go.mod" "success" ""
    else
        echo -e "    ${YELLOW}✗${NC} Go modules upgrade failed"
        audit_log "upgrade_go" "go.mod" "failure" ""
    fi
fi

# Generate diff summary
echo ""
echo "[upgrade-deps] Generating diff summary..."

DIFF_FILE="${SNAPSHOT_PATH}/diff-summary.txt"
echo "Dependency Upgrade Summary - $(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "${DIFF_FILE}"
echo "" >> "${DIFF_FILE}"

if [[ -f "${SNAPSHOT_PATH}/requirements.txt.bak" ]]; then
    echo "=== Python Requirements ===" >> "${DIFF_FILE}"
    diff -u "${SNAPSHOT_PATH}/requirements.txt.bak" "${ROOT_DIR}/requirements.txt" >> "${DIFF_FILE}" || true
    echo "" >> "${DIFF_FILE}"
fi

if [[ -f "${SNAPSHOT_PATH}/package.json.bak" ]]; then
    echo "=== Node.js Packages ===" >> "${DIFF_FILE}"
    diff -u "${SNAPSHOT_PATH}/package.json.bak" "${ROOT_DIR}/package.json" >> "${DIFF_FILE}" || true
    echo "" >> "${DIFF_FILE}"
fi

if [[ -f "${SNAPSHOT_PATH}/go.mod.bak" ]]; then
    echo "=== Go Modules ===" >> "${DIFF_FILE}"
    diff -u "${SNAPSHOT_PATH}/go.mod.bak" "${ROOT_DIR}/go.mod" >> "${DIFF_FILE}" || true
    echo "" >> "${DIFF_FILE}"
fi

echo ""
echo -e "${GREEN}[upgrade-deps] Upgrade complete${NC}"
echo ""
echo "Snapshot saved to: ${SNAPSHOT_PATH}"
echo "Diff summary: ${DIFF_FILE}"
echo ""
echo "To rollback:"
echo "  ./scripts/rollback.sh ${TIMESTAMP}"
echo ""

audit_log "upgrade-deps_complete" "dependencies" "success" "${SNAPSHOT_PATH}"

exit 0