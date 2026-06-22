#!/usr/bin/env bash
# scripts/check_no_migrating.sh — 检查登记簿中是否存在 migrating 条目
# 若存在，退出码为 1（阻断 CI 合并）
# 用法: bash scripts/check_no_migrating.sh

set -euo pipefail

REGISTRY="docs/governance/capabilities_registry.md"

if [ ! -f "$REGISTRY" ]; then
    echo "ERROR: $REGISTRY not found" >&2
    exit 1
fi

if grep -q "migrating" "$REGISTRY"; then
    echo ""
    echo "FAIL: Found entries with status 'migrating' in $REGISTRY"
    echo "These entries must be resolved before merging:"
    echo ""
    grep -n "migrating" "$REGISTRY" | head -10
    echo ""
    echo "Action required: either migrate the capability to its new location"
    echo "or mark it as 'deprecated' with a reason in the registry."
    exit 1
fi

echo "PASS: No migrating entries found in $REGISTRY"
exit 0
