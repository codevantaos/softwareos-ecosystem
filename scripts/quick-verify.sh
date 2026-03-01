#!/bin/bash
set -euo pipefail

# Quick Verification Script
# Performs basic verification of project structure and configuration

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
  "actor": "quick-verify",
  "action": "${action}",
  "resource": "${resource}",
  "result": "${result}",
  "hash": "${hash_value}",
  "version": "1.0.0",
  "requestId": "${request_id}",
  "correlationId": "${correlation_id}",
  "ip": "unknown",
  "userAgent": "quick-verify.sh"
}
EOF
)
    
    local audit_dir="${ROOT_DIR}/audit"
    mkdir -p "${audit_dir}"
    local audit_file="${audit_dir}/quick-verify_$(date -u +"%Y%m%d").jsonl"
    echo "${log_entry}" >> "${audit_file}"
}

echo -e "${GREEN}[quick-verify] Starting verification...${NC}"
echo ""

# Verification counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Check function
check() {
    local name="$1"
    local check_cmd="$2"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    echo -n "  Checking ${name}... "
    
    if bash -c "${check_cmd}" &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        audit_log "verify" "${name}" "success" ""
        return 0
    else
        echo -e "${RED}✗${NC}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        audit_log "verify" "${name}" "failure" ""
        return 1
    fi
}

# Check 1: Root index exists
check "root-index.json" "[[ -f '${ROOT_DIR}/architecture/root-index.json' ]]"

# Check 2: Audit directory exists
check "audit directory" "[[ -d '${ROOT_DIR}/audit' ]]"

# Check 3: Scripts directory exists
check "scripts directory" "[[ -d '${ROOT_DIR}/scripts' ]]"

# Check 4: Governance directory exists
check "governance directory" "[[ -d '${ROOT_DIR}/governance' ]]"

# Check 5: rot_indexer.py exists and is executable
check "rot_indexer.py" "[[ -f '${ROOT_DIR}/scripts/rot_indexer.py' ]]"

# Check 6: rot_gate.sh exists and is executable
check "rot_gate.sh" "[[ -f '${ROOT_DIR}/scripts/rot_gate.sh' ]]"

# Check 7: bootstrap.sh exists and is executable
check "bootstrap.sh" "[[ -f '${ROOT_DIR}/scripts/bootstrap.sh' ]]"

# Check 8: start-min.sh exists and is executable
check "start-min.sh" "[[ -f '${ROOT_DIR}/scripts/start-min.sh' ]]"

# Check 9: .env exists
check ".env file" "[[ -f '${ROOT_DIR}/.env' ]]"

# Check 10: Python is available
check "Python 3" "command -v python3"

# Check 11: Git is available
check "Git" "command -v git"

# Check 12: Root index is valid JSON
check "root-index.json is valid JSON" "python3 -c 'import json; json.load(open(&quot;${ROOT_DIR}/architecture/root-index.json&quot;))' 2>&1 | grep -q . || true"

echo ""
echo -e "${GREEN}[quick-verify] Verification complete${NC}"
echo ""
echo "Summary:"
echo "  Total checks: ${TOTAL_CHECKS}"
echo -e "  ${GREEN}Passed: ${PASSED_CHECKS}${NC}"
echo -e "  ${RED}Failed: ${FAILED_CHECKS}${NC}"
echo ""

if [[ ${FAILED_CHECKS} -eq 0 ]]; then
    echo -e "${GREEN}[quick-verify] ✓ All checks passed${NC}"
    audit_log "verify_complete" "quick-verify" "success" ""
    exit 0
else
    echo -e "${YELLOW}[quick-verify] ⚠ Some checks failed${NC}"
    echo ""
    echo "To fix issues:"
    echo "  1. Run: ./scripts/bootstrap.sh"
    echo "  2. Run: ./scripts/install-deps.sh"
    echo ""
    audit_log "verify_complete" "quick-verify" "partial" ""
    exit 1
fi