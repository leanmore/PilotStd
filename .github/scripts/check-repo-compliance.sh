#!/bin/bash
# 入仓合规检查 —— 对本次 push 新增文件逐项对照五条标准
set -euo pipefail

BASE_BRANCH="${BASE_BRANCH:-main}"

echo "=== 入仓合规检查 | BASE: $BASE_BRANCH ==="

git fetch origin "$BASE_BRANCH" --depth=1 2>/dev/null || true

NEW_FILES=$(git diff --name-only --diff-filter=A "origin/${BASE_BRANCH}..HEAD" 2>/dev/null || true)

if [ -z "$NEW_FILES" ]; then
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
echo "结论: PASS"
exit 0
