#!/bin/bash
#
# 產生完整目錄結構圖譜
# Generate Complete Directory Structure Diagram
#
# 此腳本會掃描專案目錄並產生完整的目錄樹結構圖
# This script scans the project directory and generates a complete directory tree structure
#
# 使用方式 / Usage:
#   ./scripts/generate-directory-tree.sh
#   ./scripts/generate-directory-tree.sh > DIRECTORY_STRUCTURE.md
#

set -euo pipefail


# 專案根目錄 / Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 需要排除的目錄 / Directories to exclude
EXCLUDE_DIRS=(
  "node_modules"
  ".git"
  "dist"
  "build"
  "coverage"
  ".next"
  ".cache"
  "__pycache__"
)

# 需要排除的檔案模式 / File patterns to exclude
EXCLUDE_FILES=(
  "*.pyc"
  ".DS_Store"
  "*.log"
)

# 特殊目錄清單（會另外標註）/ Special directories (will be noted separately)
SPECIAL_DIRS=(
  ".git"
  ".github"
  ".vscode"
  "config/dev"
  ".config"
  "config/autofix"
  ".docker-templates"
  ".ci"
  "node_modules"
)

echo "# SLASolve 專案目錄結構圖譜"
echo ""
echo "> 產生時間 / Generated at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "> 專案根目錄 / Project root: \`${PROJECT_ROOT}\`"
echo ""
echo "---"
echo ""

echo "## 📂 完整目錄結構 / Complete Directory Structure"
echo ""
echo '```'

# 使用 tree 命令（如果可用）或 find 命令
if command -v tree &> /dev/null; then
  # 建立排除參數陣列 / Build exclude parameters array
  TREE_ARGS=(-a -L 5 --dirsfirst)
  for dir in "${EXCLUDE_DIRS[@]}"; do
    TREE_ARGS+=(-I "${dir}")
  done
  for file in "${EXCLUDE_FILES[@]}"; do
    TREE_ARGS+=(-I "${file}")
  done
  
  # 執行 tree 命令 / Execute tree command
  tree "${TREE_ARGS[@]}" .
else
  # 使用 find 作為備選方案 / Use find as fallback
  echo "."
  
  # 建立排除條件陣列 / Build exclude conditions array
  FIND_ARGS=()
  FIND_ARGS+=(".")
  
  # 添加目錄排除條件
  for dir in "${EXCLUDE_DIRS[@]}"; do
    FIND_ARGS+=(-path "*/${dir}" -prune -o)
  done
  
  # 添加檔案排除條件
  for file in "${EXCLUDE_FILES[@]}"; do
    FIND_ARGS+=(-name "${file}" -prune -o)
  done
  
  # 添加列印條件並執行
  FIND_ARGS+=(-print)
  find "${FIND_ARGS[@]}" | sed -e 's;[^/]*/;|____;g;s;____|; |;g' | sort
fi

echo '```'
echo ""

echo "## 📋 特殊目錄說明 / Special Directories"
echo ""
echo "以下為特殊目錄及其用途說明："
echo ""

# 檢查並說明特殊目錄 / Check and describe special directories
declare -A SPECIAL_DIR_DESC=(
  [".git"]="Git 版本控制目錄 / Git version control directory"
  [".github"]="GitHub 設定與工作流程 / GitHub configuration and workflows"
  [".vscode"]="VS Code 編輯器設定 / VS Code editor configuration"
  ["config/dev"]="開發容器設定 / Development container configuration"
  [".config"]="專案設定檔案 / Project configuration files"
  ["config/autofix"]="自動修復機制設定 / Auto-fix mechanism configuration"
  [".docker-templates"]="Docker 範本檔案 / Docker template files"
  [".ci"]="CI 策略閘門設定 / CI policy gate configuration"
  ["node_modules"]="Node.js 依賴套件（已排除顯示）/ Node.js dependencies (excluded from display)"
)

for dir in "${SPECIAL_DIRS[@]}"; do
  if [ -d "$dir" ]; then
    desc="${SPECIAL_DIR_DESC[$dir]:-無說明 / No description}"
    echo "- **\`${dir}/\`**: ${desc}"
    
    # 顯示該目錄的第一層結構 / Show first-level structure
    if [ "$dir" != "node_modules" ] && [ "$dir" != ".git" ]; then
      if [ "$(ls -A "$dir" 2>/dev/null)" ]; then
        echo "  \`\`\`"
        ls -1 "$dir" 2>/dev/null | head -10 | sed 's/[`$\\]/\\&/g'
        file_count=$(ls -1 "$dir" 2>/dev/null | wc -l)
        if [ "$file_count" -gt 10 ]; then
          echo "  ... (共 ${file_count} 個項目 / Total ${file_count} items)"
        fi
        echo "  \`\`\`"
      fi
    fi
  fi
done

echo ""
echo "## 📊 專案統計 / Project Statistics"
echo ""

# 計算統計資訊 / Calculate statistics
total_files=$(find . -type f \( -not -path "./node_modules/*" -not -path "./.git/*" -not -path "*/dist/*" -not -path "*/build/*" \) | wc -l)
total_dirs=$(find . -type d \( -not -path "./node_modules/*" -not -path "./.git/*" -not -path "*/dist/*" -not -path "*/build/*" \) | wc -l)

echo "- **總檔案數 / Total files**: ${total_files}"
echo "- **總目錄數 / Total directories**: ${total_dirs}"
echo ""

# 依檔案類型統計 / Statistics by file type
echo "### 檔案類型分布 / File Type Distribution"
echo ""
echo "| 檔案類型 / File Type | 數量 / Count |"
echo "|---------------------|--------------|"

find . -type f \( -not -path "./node_modules/*" -not -path "./.git/*" -not -path "*/dist/*" \) | \
  awk -F/ '{print $NF}' | \
  awk -F. '{if (NF>1 && $NF!="") print "."$NF; else print "no-ext"}' | \
  sort | uniq -c | sort -rn | head -15 | \
  while read -r count ext; do
    printf "| %-17s | %12s |\n" "$ext" "$count"
  done

echo ""

# 最大的目錄 / Largest directories
echo "### 最大的目錄 / Largest Directories (排除 node_modules)"
echo ""
echo "| 目錄 / Directory | 檔案數 / File Count |"
echo "|-----------------|---------------------|"

find . -type d \( -not -path "./node_modules/*" -not -path "./.git/*" -not -path "*/dist/*" \) | \
  while read dir; do
    count=$(find "$dir" -maxdepth 1 -type f 2>/dev/null | wc -l)
    echo "$count $dir"
  done | sort -rn | head -10 | \
  while read -r count dir; do
    printf "| %-30s | %19s |\n" "\`${dir}\`" "$count"
  done

echo ""
echo "## 🔍 目錄用途說明 / Directory Purpose Description"
echo ""

# 主要目錄說明 / Main directory descriptions
declare -A DIR_DESC=(
  ["core"]="核心平台服務 / Core platform services"
  ["mcp-servers"]="MCP 伺服器實作 / MCP server implementations"
  ["scripts"]="自動化腳本 / Automation scripts"
  ["docs"]="文件資料 / Documentation"
  ["k8s"]="Kubernetes 部署設定 / Kubernetes deployment configuration"
  ["agent"]="代理程式 / Agent programs"
  ["automation-architect"]="自動化架構 / Automation architecture"
  ["autonomous-system"]="自主系統 / Autonomous system"
  ["intelligent-automation"]="智能自動化 / Intelligent automation"
  ["intelligent-hyperautomation"]="智能超自動化 / Intelligent hyperautomation"
  ["schemas"]="資料結構定義 / Schema definitions"
  ["test-vectors"]="測試向量 / Test vectors"
  ["monitoring"]="監控設定 / Monitoring configuration"
  ["governance"]="治理規則 / Governance rules"
  ["policy"]="政策定義 / Policy definitions"
  ["sbom"]="軟體物料清單 / Software Bill of Materials"
  ["audit"]="稽核記錄 / Audit logs"
  ["reports"]="報告產出 / Report outputs"
  ["runbooks"]="運維手冊 / Operational runbooks"
  ["artifacts"]="建置產物 / Build artifacts"
  ["config"]="設定檔案 / Configuration files"
  ["tools"]="工具程式 / Utility tools"
  ["softwareos-contracts"]="合約定義 / Contract definitions"
  ["advanced-system-src"]="進階系統源碼 / Advanced system source code"
  ["advanced-system-dist"]="進階系統編譯產出 / Advanced system distribution"
  ["advanced-architecture"]="進階架構 / Advanced architecture"
  ["attest-build-provenance-main"]="建置認證主程式 / Build attestation main program"
)

shopt -s nullglob
for dir in */; do
  dir="${dir%/}"  # 移除尾部斜線
  if [ -d "$dir" ] && [[ ! " ${SPECIAL_DIRS[@]} " =~ " ${dir} " ]]; then
    desc="${DIR_DESC[$dir]:-}"
    if [ -n "$desc" ]; then
      echo "- **\`${dir}/\`**: ${desc}"
    fi
  fi
done

echo ""
echo "---"
echo ""
echo "> 💡 **注意 / Note**: 此目錄結構圖譜已排除 \`node_modules\`, \`.git\`, \`dist\`, \`build\` 等目錄以提高可讀性。"
echo "> 若需查看完整結構（包含所有目錄），請執行："
echo "> \`\`\`bash"
echo "> tree -a -L 5"
echo "> # 或 / or"
echo "> find . | sed 's,[^/]*/,  ,g'"
echo "> \`\`\`"
echo ""
echo "---"
echo ""
echo "**產生腳本 / Generated by**: \`scripts/generate-directory-tree.sh\`  "
echo "**專案 / Project**: SLASolve  "
echo "**儲存庫 / Repository**: [we-can-fix/slasolve](https://github.com/we-can-fix/slasolve)"
