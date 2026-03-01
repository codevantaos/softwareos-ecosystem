#!/bin/bash
set -euo pipefail

# Install Dependencies Script
# Installs required dependencies for the project

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
  "actor": "install-deps",
  "action": "${action}",
  "resource": "${resource}",
  "result": "${result}",
  "hash": "${hash_value}",
  "version": "1.0.0",
  "requestId": "${request_id}",
  "correlationId": "${correlation_id}",
  "ip": "unknown",
  "userAgent": "install-deps.sh"
}
EOF
)
    
    local audit_dir="${ROOT_DIR}/audit"
    mkdir -p "${audit_dir}"
    local audit_file="${audit_dir}/install-deps_$(date -u +"%Y%m%d").jsonl"
    echo "${log_entry}" >> "${audit_file}"
}

echo -e "${GREEN}[install-deps] Installing dependencies...${NC}"
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    PKG_MANAGER="apt"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    PKG_MANAGER="brew"
else
    echo -e "${RED}[install-deps] Unsupported OS: ${OSTYPE}${NC}"
    audit_log "detect_os" "${OSTYPE}" "failure" ""
    exit 1
fi

audit_log "detect_os" "${OS}" "success" ""

# Install Python dependencies
echo "[install-deps] Installing Python dependencies..."
if pip3 install --upgrade pip pyyaml &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} pyyaml"
    audit_log "install_python_dep" "pyyaml" "success" ""
else
    echo -e "  ${RED}✗${NC} pyyaml (failed)"
    audit_log "install_python_dep" "pyyaml" "failure" ""
fi

# Install Node.js dependencies (if package.json exists)
if [[ -f "${ROOT_DIR}/package.json" ]]; then
    echo "[install-deps] Installing Node.js dependencies..."
    if command -v npm &> /dev/null; then
        if npm install &> /dev/null; then
            echo -e "  ${GREEN}✓${NC} npm packages"
            audit_log "install_node_deps" "npm" "success" ""
        else
            echo -e "  ${YELLOW}✗${NC} npm packages (failed)"
            audit_log "install_node_deps" "npm" "failure" ""
        fi
    else
        echo -e "  ${YELLOW}✗${NC} npm not found"
        audit_log "install_node_deps" "npm" "skipped" ""
    fi
fi

# Install Go dependencies (if go.mod exists)
if [[ -f "${ROOT_DIR}/go.mod" ]]; then
    echo "[install-deps] Installing Go dependencies..."
    if command -v go &> /dev/null; then
        if go mod download &> /dev/null; then
            echo -e "  ${GREEN}✓${NC} go modules"
            audit_log "install_go_deps" "go" "success" ""
        else
            echo -e "  ${YELLOW}✗${NC} go modules (failed)"
            audit_log "install_go_deps" "go" "failure" ""
        fi
    else
        echo -e "  ${YELLOW}✗${NC} go not found"
        audit_log "install_go_deps" "go" "skipped" ""
    fi
fi

# Install CLI tools
echo "[install-deps] Installing CLI tools..."

# Install jq (JSON processor)
if ! command -v jq &> /dev/null; then
    echo "  Installing jq..."
    if [[ "${OS}" == "linux" ]]; then
        if sudo apt-get update -qq && sudo apt-get install -y -qq jq &> /dev/null; then
            echo -e "    ${GREEN}✓${NC} jq"
            audit_log "install_cli_tool" "jq" "success" ""
        else
            echo -e "    ${YELLOW}✗${NC} jq (failed)"
            audit_log "install_cli_tool" "jq" "failure" ""
        fi
    elif [[ "${OS}" == "macos" ]]; then
        if brew install jq &> /dev/null; then
            echo -e "    ${GREEN}✓${NC} jq"
            audit_log "install_cli_tool" "jq" "success" ""
        else
            echo -e "    ${YELLOW}✗${NC} jq (failed)"
            audit_log "install_cli_tool" "jq" "failure" ""
        fi
    fi
else
    echo -e "  ${GREEN}✓${NC} jq (already installed)"
    audit_log "install_cli_tool" "jq" "skipped" ""
fi

# Install yq (YAML processor)
if ! command -v yq &> /dev/null; then
    echo "  Installing yq..."
    if wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 &> /dev/null; then
        chmod +x /usr/local/bin/yq
        echo -e "    ${GREEN}✓${NC} yq"
        audit_log "install_cli_tool" "yq" "success" ""
    else
        echo -e "    ${YELLOW}✗${NC} yq (failed)"
        audit_log "install_cli_tool" "yq" "failure" ""
    fi
else
    echo -e "  ${GREEN}✓${NC} yq (already installed)"
    audit_log "install_cli_tool" "yq" "skipped" ""
fi

# Install gh (GitHub CLI)
if ! command -v gh &> /dev/null; then
    echo "  Installing gh..."
    if [[ "${OS}" == "linux" ]]; then
        if sudo apt-get install -y -qq gh &> /dev/null; then
            echo -e "    ${GREEN}✓${NC} gh"
            audit_log "install_cli_tool" "gh" "success" ""
        else
            echo -e "    ${YELLOW}✗${NC} gh (failed)"
            audit_log "install_cli_tool" "gh" "failure" ""
        fi
    elif [[ "${OS}" == "macos" ]]; then
        if brew install gh &> /dev/null; then
            echo -e "    ${GREEN}✓${NC} gh"
            audit_log "install_cli_tool" "gh" "success" ""
        else
            echo -e "    ${YELLOW}✗${NC} gh (failed)"
            audit_log "install_cli_tool" "gh" "failure" ""
        fi
    fi
else
    echo -e "  ${GREEN}✓${NC} gh (already installed)"
    audit_log "install_cli_tool" "gh" "skipped" ""
fi

echo ""
echo -e "${GREEN}[install-deps] Installation complete${NC}"
echo ""
echo "Next steps:"
echo "  1. Run: ./scripts/bootstrap.sh"
echo "  2. Run: ./scripts/quick-verify.sh"
echo ""

audit_log "install-deps_complete" "dependencies" "success" ""

exit 0