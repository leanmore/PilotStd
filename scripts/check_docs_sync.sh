#!/bin/bash
# check_docs_sync.sh — 文档同步检查（渐进式部署，仅提醒不阻断）
#
# 检查本次提交变更的源文件，确认对应文档是否同步更新。
# 退出码始终为 0（仅提醒），待稳定后可升级为 exit 1 阻断。

set -euo pipefail

# ── 映射规则：源文件路径模式 → 对应文档（与 documentation-policy.md 触发规则表一致） ──
declare -A DOC_MAP=(
  # API 端点变更
  ["docker/api/"]="docs/specs/功能规格说明书.md"
  # 核心模块变更
  ["pilotstd/core/"]="docs/architecture/governance-summary.md"
  ["pilotstd/manager/"]="docs/architecture/governance-summary.md"
  # Docker 基础设施（API 除外）
  ["docker/auth.py"]="docs/architecture/governance-summary.md"
  ["docker/app.py"]="docs/architecture/governance-summary.md"
  ["docker/users.py"]="docs/architecture/governance-summary.md"
  # Web 前端
  ["web/src/"]="docs/specs/功能规格说明书.md"
  # 环境变量 / 配置文件
  [".env"]="docs/development/documentation-policy.md"
  [".github/workflows/ci.yml"]="docs/development/documentation-policy.md"
  # 门禁规则
  ["scripts/check_gate_"]="docs/development/documentation-policy.md"
  # DB Schema / 迁移
  ["pilotstd/core/db/"]="docs/architecture/technical-debt-registry.md"
  # 测试策略
  ["tests/"]="docs/development/documentation-policy.md"
)

# ── 变更阈值（行数超过此值才提醒） ──
MIN_CHANGE_LINES=20

# ── 获取本次提交变更的源文件 ──
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)

if [ -z "$CHANGED_FILES" ]; then
  echo "[docs-sync] 无源文件变更，跳过文档同步检查。"
  exit 0
fi

# ── 获取本次提交变更的文档文件列表（用于交叉比对） ──
CHANGED_DOCS=$(echo "$CHANGED_FILES" | grep "^docs/" || true)

# ── 筛除不需要检查的文件 ──
WARNINGS=0
CHECKED=0

while IFS= read -r file; do
  [ -z "$file" ] && continue

  # 跳过测试文件
  [[ "$file" == tests/* ]] && continue
  # 跳过 CI/配置文件
  [[ "$file" == .github/* ]] && continue
  [[ "$file" == scripts/* ]] && continue
  # 跳过文档本身
  [[ "$file" == docs/* ]] && continue
  # 跳过纯数据/配置文件
  [[ "$file" == *.json ]] && continue
  [[ "$file" == *.yml ]] && continue
  [[ "$file" == *.yaml ]] && continue
  [[ "$file" == .env* ]] && continue
  [[ "$file" == .gitignore ]] && continue
  [[ "$file" == .pre-commit-config.yaml ]] && continue
  # 跳过 __init__.py 和版本号等元数据文件
  [[ "$(basename "$file")" == "__init__.py" ]] && continue
  [[ "$(basename "$file")" == "__version__.py" ]] && continue

  # 计算变更行数
  diff_lines=$(git diff --cached -- "$file" 2>/dev/null | grep -c "^[+-]" || echo 0)

  # 如果变更行数少于阈值，跳过
  if [ "$diff_lines" -lt "$MIN_CHANGE_LINES" ]; then
    continue
  fi

  CHECKED=$((CHECKED + 1))

  # 查找匹配的文档映射
  matched_doc=""
  for prefix in "${!DOC_MAP[@]}"; do
    if [[ "$file" == "$prefix"* ]]; then
      matched_doc="${DOC_MAP[$prefix]}"
      break
    fi
  done

  # 无映射规则的源文件，跳过
  [ -z "$matched_doc" ] && continue

  # 检查对应文档是否在本次变更中
  doc_updated=false
  if echo "$CHANGED_DOCS" | grep -qF "$matched_doc"; then
    doc_updated=true
  fi

  if [ "$doc_updated" = false ]; then
    WARNINGS=$((WARNINGS + 1))
    echo "⚠ 文档同步提醒: $file 已修改 ($diff_lines 行)"
    echo "  对应文档: $matched_doc 未在本次提交中更新。"
    echo ""
  fi

done <<< "$CHANGED_FILES"

# ── 输出 ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[docs-sync] 检查完成: $CHECKED 个文件变更超阈值, $WARNINGS 处文档待同步"
if [ "$WARNINGS" -gt 0 ]; then
  echo "[docs-sync] 提示: 请确认上述变更是否需要更新对应文档。"
  echo "[docs-sync] 详见 docs/development/documentation-policy.md"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0
