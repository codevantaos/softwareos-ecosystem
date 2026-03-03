#!/bin/bash
# 結構驗證腳本
# 驗證關鍵模組是否仍然可訪問

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  結構驗證"
echo "========================================"
echo ""

ERRORS=0

# 檢查 Python 模組
echo "檢查 Python 模組..."

# 檢查 core 模組
if [ -f "workspace/src/core/__init__.py" ]; then
    echo -e "${GREEN}✅${NC} core/__init__.py 存在"
else
    echo -e "${RED}❌${NC} core/__init__.py 不存在"
    ERRORS=$((ERRORS+1))
fi

# 檢查 softwareos-contracts 模組
if [ -d "workspace/src/softwareos-contracts" ]; then
    echo -e "${GREEN}✅${NC} softwareos-contracts/ 存在"
else
    echo -e "${YELLOW}⚠️${NC}  softwareos-contracts/ 不存在"
fi

# 檢查 services 模組
if [ -d "workspace/src/services" ]; then
    echo -e "${GREEN}✅${NC} services/ 存在"
else
    echo -e "${YELLOW}⚠️${NC}  services/ 不存在"
fi

# 檢查 apps 模組
if [ -d "workspace/src/apps" ]; then
    echo -e "${GREEN}✅${NC} apps/ 存在"
else
    echo -e "${YELLOW}⚠️${NC}  apps/ 不存在"
fi

# 檢查 sacred-modules 模組
if [ -d "workspace/src/sacred-modules" ]; then
    echo -e "${GREEN}✅${NC} sacred-modules/ 存在"
else
    echo -e "${YELLOW}⚠️${NC}  sacred-modules/ 不存在"
fi

# 檢查 _sandbox 模組
if [ -d "workspace/src/_sandbox" ]; then
    echo -e "${GREEN}✅${NC} _sandbox/ 存在"
else
    echo -e "${YELLOW}⚠️${NC}  _sandbox/ 不存在"
fi

echo ""
echo "檢查目錄結構..."

# 檢查沒有中文目錄
CHINESE_DIRS=$(find workspace/src/ -maxdepth 1 -type d -name "*[一-龥]*" 2>/dev/null || true)
if [ -z "$CHINESE_DIRS" ]; then
    echo -e "${GREEN}✅${NC} 無中文目錄名稱"
else
    echo -e "${RED}❌${NC} 發現中文目錄："
    echo "$CHINESE_DIRS"
    ERRORS=$((ERRORS+1))
fi

# 檢查沒有 .egg-info 目錄
EGG_INFO=$(find workspace/src/ -name "*.egg-info" 2>/dev/null || true)
if [ -z "$EGG_INFO" ]; then
    echo -e "${GREEN}✅${NC} 無 .egg-info 目錄"
else
    echo -e "${RED}❌${NC} 發現 .egg-info 目錄："
    echo "$EGG_INFO"
    ERRORS=$((ERRORS+1))
fi

echo ""
echo "檢查配置文件..."

# 檢查 .gitignore
if [ -f ".gitignore" ]; then
    if grep -q "*.egg-info/" .gitignore; then
        echo -e "${GREEN}✅${NC} .gitignore 包含 *.egg-info/"
    fi
    
    if grep -q "__pycache__/" .gitignore; then
        echo -e "${GREEN}✅${NC} .gitignore 包含 __pycache__/"
    fi
    
    if grep -q "*.pyc" .gitignore; then
        echo -e "${GREEN}✅${NC} .gitignore 包含 *.pyc"
    fi
fi

echo ""
echo "========================================"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ 所有檢查通過！${NC}"
    exit 0
else
    echo -e "${RED}❌ 發現 $ERRORS 個錯誤${NC}"
    exit 1
fi