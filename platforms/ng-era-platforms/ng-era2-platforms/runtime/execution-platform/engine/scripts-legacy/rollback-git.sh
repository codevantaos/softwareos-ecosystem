#!/bin/bash
# 回滾腳本 - 緊急恢復
# 使用方法：./scripts/rollback.sh

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  MachineNativeOps 回滾腳本${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# 1. 恢復 Git 標籤
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_info "查找最新的備份標籤..."
LATEST_TAG=$(git tag -l "pre-refactor-*" | tail -1)

if [ -z "$LATEST_TAG" ]; then
    echo -e "${RED}❌ 未找到備份標籤${NC}"
    exit 1
fi

echo -e "${GREEN}找到標籤：$LATEST_TAG${NC}"
read -p "是否恢復到此標籤？(y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "取消回滾"
    exit 0
fi

echo -e "${YELLOW}執行 Git reset...${NC}"
git reset --hard $LATEST_TAG

echo -e "${GREEN}✅ 已恢復到 Git 標籤：$LATEST_TAG${NC}"

# 2. 恢復文件系統備份（如果有）
if [ -f ".last-backup" ]; then
    BACKUP_DIR=$(cat .last-backup)
    
    if [ -d "$BACKUP_DIR" ]; then
        echo ""
        echo -e "${GREEN}找到文件系統備份：$BACKUP_DIR${NC}"
        echo ""
        read -p "是否恢復文件系統備份？(y/n) " -n 1 -r
        echo
        
        if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
            # 恢復關鍵目錄
            if [ -d "$BACKUP_DIR/core" ]; then
                echo -e "${YELLOW}恢復 workspace/src/core/...${NC}"
                rm -rf workspace/src/core
                cp -r "$BACKUP_DIR/core" workspace/src/
            fi
            
            if [ -d "$BACKUP_DIR/softwareos-contracts" ]; then
                echo -e "${YELLOW}恢復 workspace/src/softwareos-contracts/...${NC}"
                rm -rf workspace/src/softwareos-contracts
                cp -r "$BACKUP_DIR/softwareos-contracts" workspace/src/
            fi
            
            if [ -d "$BACKUP_DIR/web" ]; then
                echo -e "${YELLOW}恢復 workspace/src/web/...${NC}"
                rm -rf workspace/src/web
                cp -r "$BACKUP_DIR/web" workspace/src/
            fi
            
            echo -e "${GREEN}✅ 文件系統備份已恢復${NC}"
        fi
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  回滾完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "建議檢查："
echo "  1. 運行測試套件：npm test && pytest"
echo "  2. 檢查 Git 狀態：git status"
echo "  3. 驗證應用程式是否正常運行"