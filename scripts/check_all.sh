#!/usr/bin/env bash
# PilotStd 本地门禁预检脚本
# 用途：在 git commit 前拦截所有可本地执行的门禁
# 原则：快速失败。重量级测试交由 CI 处理。

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🚀 [PilotStd] 开始本地门禁预检..."
echo "----------------------------------"

# 1. G-031 静态代码与类型检查 (Ruff + Mypy)
echo -e "${YELLOW}[1/6] 检查 Ruff & Mypy...${NC}"
ruff check . || { echo -e "${RED}❌ Ruff 检查失败，请修复后重试。${NC}"; exit 1; }
mypy . || { echo -e "${RED}❌ Mypy 类型检查失败，请修复后重试。${NC}"; exit 1; }

# 2. G-010 单文件行数检查 (限制 400 行)
echo -e "${YELLOW}[2/6] 检查单文件行数 (G-010)...${NC}"
OVERSIZED_FILES=$(find pilotstd -type f -name "*.py" -exec wc -l {} + | awk '$1 > 400 && $2 != "total" {print $2 " (" $1 " lines)"}')
if [ -n "$OVERSIZED_FILES" ]; then
    echo -e "${RED}❌ 发现超过 400 行的文件 (G-010 违规):${NC}"
    echo "$OVERSIZED_FILES"
    exit 1
fi

# 3. G-020 死引用/未使用代码检查 (Vulture)
echo -e "${YELLOW}[3/6] 检查 Python 死代码 (G-020)...${NC}"
vulture pilotstd/ --min-confidence 80 || { echo -e "${RED}❌ 发现疑似死代码，请清理或添加白名单。${NC}"; exit 1; }

# 4. Schema 一致性检查
echo -e "${YELLOW}[4/6] 检查 Schema 一致性...${NC}"
python scripts/check_schema_consistency.py
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Schema 不一致，请同步测试表结构后重新提交。${NC}"
    exit 1
fi

# 5. G-037 触发条件对齐检查
echo -e "${YELLOW}[5/6] 检查触发条件对齐 (G-037)...${NC}"
python scripts/check_g_037_trigger_alignment.py || { echo -e "${RED}❌ 触发条件表与 index.md 不对齐，请修复后重试。${NC}"; exit 1; }

# 6. G-038 历史遗留错误清零
echo -e "${YELLOW}[6/6] 检查历史遗留错误清零 (G-038)...${NC}"
python scripts/check_g_038_legacy_errors.py || { echo -e "${RED}❌ 存在历史遗留错误，必须当场修复。${NC}"; exit 1; }

echo "----------------------------------"
echo -e "${GREEN}✅ [PilotStd] 所有本地门禁检查通过！${NC}"
