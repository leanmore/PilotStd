#!/bin/bash
# 入仓合规检查 —— 对本次 push 新增文件逐项对照五条标准
set -euo pipefail

BASE_BRANCH="${BASE_BRANCH:-main}"

echo "=== 入仓合规检查 | BASE: $BASE_BRANCH ==="

# R11-3b：此处原为 `--depth=1`，会在 tip 处建立浅边界（.git/shallow）——后续任何基于
#   历史范围的检查（docs-sync 的 HEAD~1..HEAD 回退、本脚本自身的范围取值）都会被截断，
#   表现为「范围恒空 → 假绿」。checkout 已是 fetch-depth: 0 全量，故改为普通 fetch（行为等价、不再截断历史）。
#
# ── 范围取值（T-27 / R14-1，2026-10-01）────────────────────────────────
# 事故：原实现用 `origin/<base>..HEAD` 取“本次新增文件”，但**推送事件**触发时 origin/<base>
#   已被 CI 推进到本次 tip → 范围恒空 → 恒打印 `PASS: 无新增文件`（假绿；白名单/黑名单/
#   根目录可疑文件判定**从未在推送路径生效**，CI 日志实证 run 36304263963 / 36306033918）。
# 修法（与 docs-sync 的 T-25/R11-3b 同一手法）：由 workflow 显式传 `COMPLIANCE_RANGE=before..sha`
#   （push 载荷里 `event.before` + 通用 `github.sha`）；未提供时回退 PR/本地口径
#   `origin/<base>...HEAD`（三点＝与基线 merge-base 比较，等价于 PR 的 changed files）。
# 另加**假绿防护**：显式范围若“变更文件数 == 0”，直接 FAIL —— 门卫宁可报错，不可静默放行。
ZERO_SHA="0000000000000000000000000000000000000000"
RANGE_EXPECT_NONEMPTY=0
RANGE="${COMPLIANCE_RANGE:-}"
if [ -n "$RANGE" ]; then
  LEFT="${RANGE%%..*}"
  if [ -z "$LEFT" ] || [ "$LEFT" = "$ZERO_SHA" ]; then
    # 新建分支/首次推送：before 为全零，没有“本次推送”可比 → 回退到基线口径
    RANGE=""
  else
    RANGE_EXPECT_NONEMPTY=1
  fi
fi
if [ -z "$RANGE" ]; then
  git fetch origin "$BASE_BRANCH" --no-tags 2>/dev/null || true
  RANGE="origin/${BASE_BRANCH}...HEAD"
fi

CHANGED_COUNT=$(git diff --name-only "$RANGE" 2>/dev/null | grep -c . || true)
# --diff-filter=AR：A=新增、R=改名（改名后的目标路径同样是“新入仓路径”，不得借改名绕过判定）
NEW_FILES=$(git diff --name-only --diff-filter=AR "$RANGE" 2>/dev/null || true)
NEW_COUNT=$(printf '%s\n' "$NEW_FILES" | grep -c . || true)

echo "范围: $RANGE（变更 ${CHANGED_COUNT} 个文件，其中新增/改名 ${NEW_COUNT} 个）"

if [ "$RANGE_EXPECT_NONEMPTY" = "1" ] && [ "$CHANGED_COUNT" -eq 0 ]; then
  echo "❌ FAIL: 显式范围 $RANGE 内变更文件数为 0 —— 范围取值异常（假绿防护：拒绝 PASS）"
  exit 1
fi

if [ "$NEW_COUNT" -eq 0 ]; then
  echo "PASS: 无新增文件"
  exit 0
fi

echo "$NEW_FILES"
echo "========================================="

# ── 白名单 ──
WHITELIST_PREFIXES=(
  "pilotstd/" "docker/" "web/src/" "tests/" ".github/"
  "docs/architecture/" "docs/specs/" "docs/development/"
  "docs/governance/" "docs/guides/" "assets/"
)
WHITELIST_EXACT=(
  "docs/index.md" "README.md" "CHANGELOG.md" "CONTRIBUTING.md"
  "LICENSE" "docker-compose.yml" ".pre-commit-config.yaml"
  "pyproject.toml" "web/pnpm-lock.yaml" "web/package-lock.json"
  "web/package.json" ".gitignore" ".dockerignore"
  ".env.example" ".secrets.baseline"
)

# ── 黑名单 ──
BLACKLIST_PREFIXES=(
  "docs/archive/" "docs/pending/" "docs/superpowers/" "reports/"
)

FILENAME_BLACKLIST=(
  "*_plan.md" "*_design.md" "*_report.md" "*_survey*.md" "*.txt"
)

# ── 辅助函数 ──
is_whitelisted() {
  local f="$1"
  for p in "${WHITELIST_PREFIXES[@]}"; do [[ "$f" == "$p"* ]] && return 0; done
  for e in "${WHITELIST_EXACT[@]}"; do [[ "$f" == "$e" ]] && return 0; done
  return 1
}

is_blacklisted_path() {
  for p in "${BLACKLIST_PREFIXES[@]}"; do [[ "$1" == "$p"* ]] && return 0; done
  return 1
}

matches_filename_blacklist() {
  local bn; bn=$(basename "$1")
  for pat in "${FILENAME_BLACKLIST[@]}"; do [[ "$bn" == $pat ]] && return 0; done
  return 1
}

is_root_suspicious() {
  [[ "$1" != */* ]] || return 1
  [[ "$1" == *.md || "$1" == *.png || "$1" == *.json ]]
}

# ── 逐文件判断 ──
FAIL_FILES=()
WARN_FILES=()
PASS_COUNT=0

while IFS= read -r file; do
  [ -z "$file" ] && continue
  if is_whitelisted "$file"; then ((PASS_COUNT++)) || true; continue; fi
  if is_blacklisted_path "$file"; then
    FAIL_FILES+=("$file | 路径命中黑名单（过程文件/内部工具目录）"); continue
  fi
  if matches_filename_blacklist "$file"; then
    FAIL_FILES+=("$file | 文件名命中过程文件模式"); continue
  fi
  if is_root_suspicious "$file"; then
    FAIL_FILES+=("$file | 根目录可疑文件（.md/.png/.json 不在白名单）"); continue
  fi
  WARN_FILES+=("$file | 存疑，需人工判断")
done <<< "$NEW_FILES"

# ── 输出 ──
echo "白名单放行: ${PASS_COUNT} 个"
[ ${#FAIL_FILES[@]} -gt 0 ] && { echo "=== FAIL ==="; for item in "${FAIL_FILES[@]}"; do echo "  ❌ $item"; done; echo; }
[ ${#WARN_FILES[@]} -gt 0 ] && { echo "=== WARNING ==="; for item in "${WARN_FILES[@]}"; do echo "  ⚠️  $item"; done; echo; }

if [ ${#FAIL_FILES[@]} -gt 0 ]; then
  echo "结论: FAIL — 存在明确违规，请移出仓库或申请例外"
  exit 1
fi

# ── G-019 扩展: 白名单路径完整性 ──
echo ""
echo "--- G-019 路径检查 ---"
GUARD_FILE="pilotstd/core/path_guard.py"
if [ -f "$GUARD_FILE" ]; then
  for required in "/inbox" "/standards"; do
    if grep -q "$required" "$GUARD_FILE" 2>/dev/null; then
      echo "  ✅ $required 在白名单中"
    else
      echo "  ❌ $required 不在白名单中！请检查 $GUARD_FILE"
      exit 1
    fi
  done
  echo "  G-019 路径检查: PASS"
else
  echo "  ⚠️  $GUARD_FILE 不存在，跳过"
fi

echo "结论: PASS"
exit 0
