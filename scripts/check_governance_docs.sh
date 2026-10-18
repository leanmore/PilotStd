#!/bin/bash
# 治理文档增量检查（原独立 workflow，2026-10-18 合并进 CI repo-compliance）
# 规范基准: docs/governance/gates.md（治理文档索引）
set -e

echo "🔍 检查 governance 文档增量变更..."

# 显式范围优先（push: before..sha；PR: base.sha..head.sha）。
# 旧实现固定 HEAD~1..HEAD：多提交推送/PR 只检查最后一笔，直推 main 时甚至可能漏检。
RANGE="${GOVERNANCE_DOCS_RANGE:-}"
if [ -n "$RANGE" ]; then
    LEFT="${RANGE%%..*}"
    ZERO_SHA="0000000000000000000000000000000000000000"
    if [ -z "$LEFT" ] || [ "$LEFT" = "$ZERO_SHA" ]; then
        RANGE=""
    fi
fi
if [ -z "$RANGE" ]; then
    if git rev-parse HEAD~1 >/dev/null 2>&1; then
        RANGE="HEAD~1..HEAD"
    fi
fi

if [ -n "$RANGE" ]; then
    CHANGED_FILES=$(git diff --name-only "$RANGE" -- docs/governance/ 2>/dev/null || echo "")
else
    CHANGED_FILES=""
fi

if [ -z "$CHANGED_FILES" ]; then
    echo "✅ 无 governance 文档变更，跳过检查。"
    exit 0
fi

echo "范围: ${RANGE}（变更文件：$(printf '%s\n' "$CHANGED_FILES" | grep -c .) 个）"

ERRORS=0
for FILE in $CHANGED_FILES; do
    if [[ "$FILE" == *.md ]]; then
        # 检查治理文档完整性
        if ! grep -qE "(最后更新|Last.updated|版本|version):" "$FILE"; then
            echo "⚠️  $FILE 缺少日期/版本元数据"
        fi
    fi
done

# 核心治理文档完整性：当前无"不可修改"白名单（gates.md 本身需随门禁演进更新）
PROTECTED_FILES=()

for PF in "${PROTECTED_FILES[@]}"; do
    if echo "$CHANGED_FILES" | grep -qF "$PF"; then
        echo "❌ 受保护治理文档被修改: $PF"
        echo "   修改需通过 [决策请求] 流程。"
        ERRORS=$((ERRORS+1))
    fi
done

if [ $ERRORS -gt 0 ]; then
    echo "❌ 发现 $ERRORS 个治理文档规范问题，请修复后重新提交。"
    exit 1
else
    echo "✅ 所有治理文档符合规范。"
    exit 0
fi
