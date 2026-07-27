#!/bin/bash
# 治理文档增量检查脚本（Phase 2 CI 使用）
# 规范基准: docs/governance/trinity-technical-spec-v2.md §5.2
set -e

echo "🔍 检查 governance 文档增量变更..."

CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD -- docs/governance/ 2>/dev/null || echo "")

if [ -z "$CHANGED_FILES" ]; then
  echo "✅ 无 governance 文档变更，跳过检查。"
  exit 0
fi

ERRORS=0
for FILE in $CHANGED_FILES; do
  if [[ "$FILE" == *.md ]]; then
    # 检查治理文档完整性
    if ! grep -qE "(最后更新|Last.updated|版本|version):" "$FILE"; then
      echo "⚠️  $FILE 缺少日期/版本元数据"
    fi
  fi
done

# 核心治理文档完整性：确保受保护文件未被修改
PROTECTED_FILES=(
    "docs/governance/prompt-crafting-guide.md"
    "docs/governance/rule-quickref.md"
    "docs/governance/development-flow.md"
    "docs/governance/trinity-technical-spec-v2.md"
)

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
