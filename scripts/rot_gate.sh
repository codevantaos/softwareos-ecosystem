#!/bin/bash
set -euo pipefail

# Root-of-Trust Gate Enforcement
# Validates that all changed files are indexed and index is up-to-date

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INDEX_FILE="${ROOT_DIR}/architecture/root-index.json"
INDEXER_SCRIPT="${SCRIPT_DIR}/rot_indexer.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Audit logging function
audit_log() {
    local action="$1"
    local resource="$2"
    local result="$3"
    local hash_value="${4:-}"
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local request_id=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")
    local correlation_id=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")
    
    local log_entry=$(cat <<EOF
{
  "timestamp": "${timestamp}",
  "actor": "rot_gate",
  "action": "${action}",
  "resource": "${resource}",
  "result": "${result}",
  "hash": "${hash_value}",
  "version": "1.0.0",
  "requestId": "${request_id}",
  "correlationId": "${correlation_id}",
  "ip": "unknown",
  "userAgent": "rot_gate.sh"
}
EOF
)
    
    local audit_dir="${ROOT_DIR}/audit"
    mkdir -p "${audit_dir}"
    local audit_file="${audit_dir}/rot_gate_$(date -u +"%Y%m%d").jsonl"
    echo "${log_entry}" >> "${audit_file}"
}

# Check if index exists
if [[ ! -f "${INDEX_FILE}" ]]; then
    echo -e "${RED}[rot_gate] ERROR: Index file not found: ${INDEX_FILE}${NC}"
    audit_log "run_gate" "${INDEX_FILE}" "failure" ""
    exit 10
fi

# Get current index hash
CURRENT_HASH=$(sha3sum "${INDEX_FILE}" 2>/dev/null | cut -d' ' -f1 || python3 -c "import hashlib; print(hashlib.sha3_512(open('${INDEX_FILE}','rb').read()).hexdigest())")

# Generate new index
echo "[rot_gate] Generating new index..."
cd "${ROOT_DIR}"
python3 "${INDEXER_SCRIPT}"

# Get new index hash
NEW_HASH=$(sha3sum "${INDEX_FILE}" 2>/dev/null | cut -d' ' -f1 || python3 -c "import hashlib; print(hashlib.sha3_512(open('${INDEX_FILE}','rb').read()).hexdigest())")

# Compare hashes
if [[ "${CURRENT_HASH}" != "${NEW_HASH}" ]]; then
    echo -e "${RED}[rot_gate] ERROR: Index is outdated. Manual edits detected or files changed without re-indexing.${NC}"
    echo -e "${YELLOW}[rot_gate] Run: python3 ${INDEXER_SCRIPT} to update the index${NC}"
    audit_log "run_gate" "${INDEX_FILE}" "failure" "${CURRENT_HASH}"
    exit 10
fi

# Check if all changed files are indexed
if [[ -n "${GITHUB_BASE_REF:-}" ]]; then
    echo "[rot_gate] Checking changed files against index..."
    
    # Get changed files
    CHANGED_FILES=$(git diff --name-only origin/"${GITHUB_BASE_REF}"...HEAD 2>/dev/null || git diff --name-only HEAD~1 HEAD)
    
    if [[ -n "${CHANGED_FILES}" ]]; then
        while IFS= read -r file; do
            # Skip non-governed files
            if [[ "${file}" =~ \.(py|sh|yml|yaml|json|rego|toml|md|txt)$ ]] || [[ "$(basename "${file}")" =~ ^(Dockerfile|Makefile)$ ]]; then
                # Check if file is in index
                if ! grep -q "&quot;path&quot;: &quot;${file}&quot;" "${INDEX_FILE}"; then
                    echo -e "${RED}[rot_gate] ERROR: File not indexed: ${file}${NC}"
                    audit_log "run_gate" "${file}" "failure" ""
                    exit 20
                fi
            fi
        done <<< "${CHANGED_FILES}"
    fi
fi

echo -e "${GREEN}[rot_gate] PASS: Index is up-to-date and all governed files are indexed${NC}"
audit_log "run_gate" "${INDEX_FILE}" "success" "${NEW_HASH}"
exit 0