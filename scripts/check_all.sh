#!/bin/bash
set -e

echo "============================================================"
echo "三位一体治理体系 - 本地检查（门禁支柱）"
echo "============================================================"

# 环境信息输出（便于排查 command not found）
echo ""
echo "Python: $(which python3 || which python)"
echo "PWD: $(pwd)"

# 检查依赖是否可用
echo ""
echo "检查工具依赖..."
for cmd in ruff mypy python; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ $cmd 未安装或不在 PATH 中"
        exit 1
    fi
done
echo "✅ 工具依赖检查通过"

echo ""
echo "[1/4] Ruff..."
ruff check .

echo ""
echo "[2/4] Mypy..."
mypy pilotstd/

echo ""
echo "[3/4] G-010 代码规模..."
python scripts/check_g_010_code_size.py

echo ""
echo "[4/4] G-011 属性完整性..."
python scripts/check_g_011_attr_integrity.py

echo ""
echo "✅ 全部检查通过"
