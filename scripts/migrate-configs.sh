#!/bin/bash
set -euo pipefail

# Migrate Configurations Script
# Migrates configuration files between versions with backup

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
  "actor": "migrate-configs",
  "action": "${action}",
  "resource": "${resource}",
  "result": "${result}",
  "hash": "${hash_value}",
  "version": "1.0.0",
  "requestId": "${request_id}",
  "correlationId": "${correlation_id}",
  "ip": "unknown",
  "userAgent": "migrate-configs.sh"
}
EOF
)
    
    local audit_dir="${ROOT_DIR}/audit"
    mkdir -p "${audit_dir}"
    local audit_file="${audit_dir}/migrate-configs_$(date -u +"%Y%m%d").jsonl"
    echo "${log_entry}" >> "${audit_file}"
}

MIGRATION_DIR="${ROOT_DIR}/.migrations"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
MIGRATION_PATH="${MIGRATION_DIR}/migration-${TIMESTAMP}"

echo -e "${GREEN}[migrate-configs] Starting configuration migration...${NC}"
echo ""

# Create migration directory
mkdir -p "${MIGRATION_PATH}"

# Backup current configurations
echo "[migrate-configs] Backing up current configurations..."

CONFIG_FILES=(
    ".env"
    "package.json"
    "requirements.txt"
    "go.mod"
    "MAINTAINERS.yaml"
    "routing-rules.yaml"
)

BACKUP_COUNT=0
for config in "${CONFIG_FILES[@]}"; do
    if [[ -f "${ROOT_DIR}/${config}" ]]; then
        cp "${ROOT_DIR}/${config}" "${MIGRATION_PATH}/${config}.bak"
        echo "  ✓ ${config}"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
        audit_log "backup" "${config}" "success" ""
    fi
done

echo ""
echo "[migrate-configs] Applying migrations..."

# Migration 1: Update .env format
if [[ -f "${MIGRATION_PATH}/.env.bak" ]]; then
    echo "  Migrating .env format..."
    
    # Check if migration needed
    if grep -q "^NODE_ENV=" "${MIGRATION_PATH}/.env.bak"; then
        echo -e "    ${YELLOW}⊘${NC} .env already migrated"
        audit_log "migrate" ".env" "skipped" ""
    else
        # Apply migration
        cp "${MIGRATION_PATH}/.env.bak" "${ROOT_DIR}/.env"
        
        # Add new variables if missing
        if ! grep -q "^LOG_LEVEL=" "${ROOT_DIR}/.env"; then
            echo "LOG_LEVEL=info" >> "${ROOT_DIR}/.env"
        fi
        
        echo -e "    ${GREEN}✓${NC} .env migrated"
        audit_log "migrate" ".env" "success" ""
    fi
fi

# Migration 2: Update MAINTAINERS.yaml format
if [[ -f "${MIGRATION_PATH}/MAINTAINERS.yaml.bak" ]]; then
    echo "  Migrating MAINTAINERS.yaml format..."
    
    # Check if migration needed
    if grep -q "apiVersion:" "${MIGRATION_PATH}/MAINTAINERS.yaml.bak"; then
        echo -e "    ${YELLOW}⊘${NC} MAINTAINERS.yaml already migrated"
        audit_log "migrate" "MAINTAINERS.yaml" "skipped" ""
    else
        # Apply migration
        python3 <<'PYEOF'
import yaml
from pathlib import Path

backup_file = Path(".migrations/migration-$(date -u +"%Y%m%dT%H%M%SZ")/MAINTAINERS.yaml.bak")
target_file = Path("MAINTAINERS.yaml")

if backup_file.exists():
    with open(backup_file, 'r') as f:
        data = yaml.safe_load(f)
    
    # Wrap in new format
    migrated = {
        'apiVersion': 'platform.rot/v1',
        'kind': 'Maintainers',
        'metadata': {
            'version': '1.0.0'
        },
        'spec': data
    }
    
    with open(target_file, 'w') as f:
        yaml.dump(migrated, f, default_flow_style=False, sort_keys=False)
PYEOF
        echo -e "    ${GREEN}✓${NC} MAINTAINERS.yaml migrated"
        audit_log "migrate" "MAINTAINERS.yaml" "success" ""
    fi
fi

# Migration 3: Update routing-rules.yaml format
if [[ -f "${MIGRATION_PATH}/routing-rules.yaml.bak" ]]; then
    echo "  Migrating routing-rules.yaml format..."
    
    # Check if migration needed
    if grep -q "apiVersion:" "${MIGRATION_PATH}/routing-rules.yaml.bak"; then
        echo -e "    ${YELLOW}⊘${NC} routing-rules.yaml already migrated"
        audit_log "migrate" "routing-rules.yaml" "skipped" ""
    else
        # Apply migration
        python3 <<'PYEOF'
import yaml
from pathlib import Path

backup_file = Path(".migrations/migration-$(date -u +"%Y%m%dT%H%M%SZ")/routing-rules.yaml.bak")
target_file = Path("routing-rules.yaml")

if backup_file.exists():
    with open(backup_file, 'r') as f:
        data = yaml.safe_load(f)
    
    # Wrap in new format
    migrated = {
        'apiVersion': 'platform.rot/v1',
        'kind': 'RoutingRules',
        'metadata': {
            'version': '1.0.0'
        },
        'spec': data
    }
    
    with open(target_file, 'w') as f:
        yaml.dump(migrated, f, default_flow_style=False, sort_keys=False)
PYEOF
        echo -e "    ${GREEN}✓${NC} routing-rules.yaml migrated"
        audit_log "migrate" "routing-rules.yaml" "success" ""
    fi
fi

# Generate migration report
echo ""
echo "[migrate-configs] Generating migration report..."

REPORT_FILE="${MIGRATION_PATH}/migration-report.txt"
cat > "${REPORT_FILE}" <<EOF
Configuration Migration Report
Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Migration ID: ${TIMESTAMP}

Summary:
  Backed up files: ${BACKUP_COUNT}
  Migration path: ${MIGRATION_PATH}

Files migrated:
EOF

for config in "${CONFIG_FILES[@]}"; do
    if [[ -f "${MIGRATION_PATH}/${config}.bak" ]]; then
        echo "  - ${config}" >> "${REPORT_FILE}"
    fi
done

echo "" >> "${REPORT_FILE}"
echo "To rollback:" >> "${REPORT_FILE}"
echo "  ./scripts/rollback.sh ${TIMESTAMP}" >> "${REPORT_FILE}"

echo ""
echo -e "${GREEN}[migrate-configs] Migration complete${NC}"
echo ""
echo "Backup saved to: ${MIGRATION_PATH}"
echo "Report: ${REPORT_FILE}"
echo ""
echo "To rollback:"
echo "  ./scripts/rollback.sh ${TIMESTAMP}"
echo ""

audit_log "migrate-configs_complete" "configurations" "success" "${MIGRATION_PATH}"

exit 0