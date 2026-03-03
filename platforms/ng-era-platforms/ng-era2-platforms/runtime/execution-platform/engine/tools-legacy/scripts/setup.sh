#!/bin/bash
# ============================================================================
# SLASolve 系統初始化腳本 (System Setup Script)
# ============================================================================
# 用途: 初始化 SLASolve 自動化架構與代碼智能系統
# 版本: 1.0.0
# ============================================================================

set -euo pipefail

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 檢查系統要求
check_requirements() {
    log_info "檢查系統要求..."
    
    local missing_deps=()
    
    # 檢查 Node.js
    if command_exists node; then
        local node_version=$(node --version | sed 's/v//')
        log_success "Node.js: $node_version"
    else
        missing_deps+=("node")
        log_warning "Node.js 未安裝 (需要 >= 18.0.0)"
    fi
    
    # 檢查 npm
    if command_exists npm; then
        local npm_version=$(npm --version)
        log_success "npm: $npm_version"
    else
        missing_deps+=("npm")
        log_warning "npm 未安裝 (需要 >= 8.0.0)"
    fi
    
    # 檢查 Python
    if command_exists python3; then
        local python_version=$(python3 --version | awk '{print $2}')
        log_success "Python: $python_version"
    else
        missing_deps+=("python3")
        log_warning "Python 3 未安裝 (需要 >= 3.9)"
    fi
    
    # 檢查 pip
    if command_exists pip3; then
        local pip_version=$(pip3 --version | awk '{print $2}')
        log_success "pip: $pip_version"
    else
        missing_deps+=("pip3")
        log_warning "pip3 未安裝"
    fi
    
    # 檢查 Git
    if command_exists git; then
        local git_version=$(git --version | awk '{print $3}')
        log_success "Git: $git_version"
    else
        missing_deps+=("git")
        log_warning "Git 未安裝"
    fi
    
    # 檢查 Docker (可選)
    if command_exists docker; then
        local docker_version=$(docker --version | awk '{print $3}' | sed 's/,//')
        log_success "Docker: $docker_version"
    else
        log_warning "Docker 未安裝 (可選，用於容器化部署)"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "缺少必要的依賴: ${missing_deps[*]}"
        log_info "請安裝缺少的依賴後重新運行此腳本"
        exit 1
    fi
    
    log_success "所有必要的依賴已安裝"
}

# 創建必要的目錄結構
create_directories() {
    log_info "創建目錄結構..."
    
    local dirs=(
        "config/autofix/rules"
        "config/autofix/templates"
        "config/autofix/validators"
        "config/autofix/transformations"
        "advanced-system-src/core/analyzers"
        "advanced-system-src/core/services"
        "advanced-system-src/core/repairers"
        "agent/code-analyzer/src"
        "agent/code-analyzer/config"
        "agent/code-analyzer/tests"
        "agent/vulnerability-detector/src"
        "agent/vulnerability-detector/config"
        "agent/vulnerability-detector/tests"
        "agent/auto-repair/src"
        "agent/auto-repair/config"
        "agent/auto-repair/templates"
        "agent/auto-repair/tests"
        "agent/orchestrator/src"
        "agent/orchestrator/config"
        "agent/orchestrator/tests"
        "intelligent-hyperautomation/workflows"
        "intelligent-hyperautomation/decision-engines"
        "intelligent-hyperautomation/feedback-loops"
        "logs"
        "reports"
        "evidence"
    )
    
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_success "創建目錄: $dir"
        else
            log_info "目錄已存在: $dir"
        fi
    done
}

# 安裝 Node.js 依賴
install_node_dependencies() {
    log_info "安裝 Node.js 依賴..."
    
    if [ -f "package.json" ]; then
        npm install
        log_success "Node.js 依賴安裝完成"
    else
        log_warning "未找到 package.json"
    fi
    
    # 安裝工作區依賴
    if [ -d "core/softwareos-contracts/softwareos-contracts-L1/softwareos-contracts" ]; then
        log_info "安裝 softwareos-contracts-L1 依賴..."
        cd core/softwareos-contracts/softwareos-contracts-L1/softwareos-contracts
        npm install
        cd - > /dev/null
        log_success "softwareos-contracts-L1 依賴安裝完成"
    fi
}

# 安裝 Python 依賴
install_python_dependencies() {
    log_info "安裝 Python 依賴..."
    
    # 創建虛擬環境
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "創建 Python 虛擬環境"
    fi
    
    # 激活虛擬環境
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        log_error "無法激活虛擬環境: venv/bin/activate 不存在"
        return 1
    fi
    
    # 升級 pip
    pip install --upgrade pip
    
    # 安裝依賴
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        log_success "Python 依賴安裝完成"
    else
        # 安裝基本依賴
        pip install \
            aiohttp \
            pydantic \
            pytest \
            pytest-asyncio \
            black \
            pylint \
            mypy
        log_success "安裝基本 Python 依賴"
    fi
    
    deactivate
}

# 配置環境變量
setup_environment() {
    log_info "配置環境變量..."
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# SLASolve 環境配置

# 系統設置
NODE_ENV=development
LOG_LEVEL=INFO
MAX_WORKERS=16

# 數據庫配置
DATABASE_URL=postgresql://localhost:5432/slasolve
REDIS_URL=redis://localhost:6379

# 安全工具配置
SONARQUBE_TOKEN=
SNYK_TOKEN=
GITHUB_TOKEN=

# 通知配置
SLACK_WEBHOOK=
SMTP_SERVER=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# 存儲配置
S3_BUCKET=
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# 監控配置
PROMETHEUS_PORT=9090
JAEGER_ENDPOINT=http://localhost:6831
LOKI_URL=http://localhost:3100
EOF
        log_success "創建 .env 文件"
        log_warning "請編輯 .env 文件並填入必要的配置"
    else
        log_info ".env 文件已存在"
    fi
}

# 初始化 Git hooks
setup_git_hooks() {
    log_info "設置 Git hooks..."
    
    if [ -d ".git" ]; then
        # Pre-commit hook
        cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Pre-commit hook for SLASolve

echo "Running pre-commit checks..."

# Lint TypeScript files
if command -v npm >/dev/null 2>&1; then
    npm run lint --if-present || true
fi

# Lint Python files
if command -v pylint >/dev/null 2>&1; then
    find . -name "*.py" -not -path "./venv/*" -not -path "./node_modules/*" | xargs pylint --exit-zero
fi

echo "Pre-commit checks completed"
EOF
        chmod +x .git/hooks/pre-commit
        log_success "Git pre-commit hook 已設置"
    else
        log_warning "不是 Git 倉庫，跳過 Git hooks 設置"
    fi
}

# 驗證安裝
verify_installation() {
    log_info "驗證安裝..."
    
    local errors=0
    
    # 檢查配置文件
    if [ -f "auto-fix-bot.yml" ]; then
        log_success "auto-fix-bot.yml 配置存在"
    else
        log_error "auto-fix-bot.yml 配置不存在"
        errors=$((errors + 1))
    fi
    
    # 檢查 schemas
    if [ -d "schemas" ] && [ "$(ls -A schemas/*.json 2>/dev/null | wc -l)" -gt 0 ]; then
        log_success "JSON schemas 存在"
    else
        log_error "JSON schemas 不存在或為空"
        errors=$((errors + 1))
    fi
    
    # 檢查 agent 結構
    for agent in code-analyzer vulnerability-detector auto-repair orchestrator; do
        if [ -d "agent/$agent" ]; then
            log_success "Agent $agent 目錄存在"
        else
            log_error "Agent $agent 目錄不存在"
            errors=$((errors + 1))
        fi
    done
    
    if [ $errors -eq 0 ]; then
        log_success "安裝驗證通過"
        return 0
    else
        log_error "安裝驗證失敗: $errors 個錯誤"
        return 1
    fi
}

# 顯示下一步提示
show_next_steps() {
    echo ""
    echo "============================================================================"
    log_success "SLASolve 系統初始化完成！"
    echo "============================================================================"
    echo ""
    echo "下一步操作："
    echo ""
    echo "1. 配置環境變量："
    echo "   ${BLUE}vi .env${NC}"
    echo ""
    echo "2. 運行代碼分析："
    echo "   ${BLUE}./scripts/analyze.sh${NC}"
    echo ""
    echo "3. 運行自動修復："
    echo "   ${BLUE}./scripts/repair.sh${NC}"
    echo ""
    echo "4. 啟動服務："
    echo "   ${BLUE}npm run build && npm start${NC}"
    echo ""
    echo "5. 查看文檔："
    echo "   - README.md"
    echo "   - agent/*/README.md"
    echo "   - docs/"
    echo ""
    echo "============================================================================"
}

# 主函數
main() {
    echo "============================================================================"
    echo "              SLASolve 系統初始化"
    echo "     Senior Automation Architect & Code Intelligence Engineer"
    echo "============================================================================"
    echo ""
    
    check_requirements
    echo ""
    
    create_directories
    echo ""
    
    install_node_dependencies
    echo ""
    
    install_python_dependencies
    echo ""
    
    setup_environment
    echo ""
    
    setup_git_hooks
    echo ""
    
    if verify_installation; then
        show_next_steps
    else
        log_error "安裝過程中出現錯誤，請檢查上面的錯誤信息"
        exit 1
    fi
}

# 執行主函數
main "$@"
