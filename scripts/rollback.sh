#!/bin/bash
set -euo pipefail

# Rollback Script
# Rolls back upgrades or migrations from snapshots

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
  "actor": "rollback",
  "action": "${action}",
  "resource": "${resource}",
  "result": "${result}",
  "hash": "${hash_value}",
  "version": "1.0.0",
  "requestId": "${request_id}",
  "correlationId": "${correlation_id}",
  "ip": "unknown",
  "userAgent": "rollback.sh"
}
EOF
)
    
    local audit_dir="${ROOT_DIR}/audit"
    mkdir -p "${audit_dir}"
    local audit_file="${audit_dir}/rollback_$(date -u +"%Y%m%d").jsonl"
    echo "${log_entry}" >> "${audit_file}"
}

# Check for timestamp argument
if [[ $# -eq 0 ]]; then
    echo -e "${RED}[rollback] Error: Timestamp required${NC}"
    echo ""
    echo "Usage: ./scripts/rollback.sh <TIMESTAMP>"
    echo ""
    echo "Available snapshots:"
    
    # List available snapshots
    if [[ -d "${ROOT_DIR}/.snapshots" ]]; then
        for snapshot in "${ROOT_DIR}/.snapshots"/upgrade-*; do
            if [[ -d "${snapshot}" ]]; then
                echo "  $(basename "${snapshot}")"
            fi
        done
    fi
    
    if [[ -d "${ROOT_DIR}/.migrations" ]]; then
        for migration in "${ROOT_DIR}/.migrations"/migration-*; do
            if [[ -d "${migration}" ]]; then
                echo "  $(basename "${migration}")"
            fi
        done
    fi
    
    echo ""
    exit 1
fi

TIMESTAMP="$1"
SNAPSHOT_PATH="${ROOT_DIR}/.snapshots/upgrade-${TIMESTAMP}"
MIGRATION_PATH="${ROOT_DIR}/.migrations/migration-${TIMESTAMP}"

# Determine which path to use
if [[ -d "${SNAPSHOT_PATH}" ]]; then
    RESTORE_PATH="${SNAPSHOT_PATH}"
    TYPE="upgrade"
elif [[ -d "${MIGRATION_PATH}" ]]; then
    RESTORE_PATH="${MIGRATION_PATH}"
    TYPE="migration"
else
    echo -e "${RED}[rollback] Error: Snapshot/migration not found: ${TIMESTAMP}${NC}"
    audit_log "rollback" "${TIMESTAMP}" "failure" ""
    exit 1
fi

echo -e "${GREEN}[rollback] Starting rollback from ${TYPE}...${NC}"
echo ""
echo "Restore path: ${RESTORE_PATH}"
echo ""

# Confirm rollback
read -p "Are you sure you want to rollback? (yes/no): " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
    echo -e "${YELLOW}[rollback] Rollback cancelled${NC}"
    audit_log "rollback" "${TIMESTAMP}" "cancelled" ""
    exit 0
fi

# Restore files
echo "[rollback] Restoring files..."

RESTORED_COUNT=0
for backup_file in "${RESTORE_PATH}"/*.bak; do
    if [[ -f "${backup_file}" ]]; then
        filename=$(basename "${backup_file}" .bak)
        target_file="${ROOT_DIR}/${filename}"
        
        # Create current backup before restoring
        if [[ -f "${target_file}" ]]; then
            cp "${target_file}" "${target_file}.pre-rollback-$(date -u +"%Y%m%dT%H%M%SZ")"
        fi
        
        # Restore from backup
        cp "${backup_file}" "${target_file}"
        echo -e "  ${GREEN}✓${NC} ${filename}"
        RESTORED_COUNT=$((RESTORED_COUNT + 1))
        audit_log "restore" "${filename}" "success" ""
    fi
done

echo ""
echo -e "${GREEN}[rollback] Rollback complete${NC}"
echo ""
echo "Restored ${RESTORED_COUNT} file(s)"
echo ""
echo "Pre-rollback backups created with .pre-rollback-* suffix"
echo ""

audit_log "rollback_complete" "${TIMESTAMP}" "success" "${RESTORE_PATH}"

exit 0