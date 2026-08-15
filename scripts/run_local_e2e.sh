#!/bin/bash
# 本地运行国内站点 E2E 测试并生成记录
# 用法: bash scripts/run_local_e2e.sh

mkdir -p reports
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

python -m pytest tests/test_e2e_adapters.py \
    -v \
    --tb=short \
    --junitxml="reports/e2e_china_${TIMESTAMP}.xml" \
    -o log_file="reports/e2e_china_${TIMESTAMP}.log"

echo ""
echo "✅ 测试记录已保存:"
echo "   JUnit XML: reports/e2e_china_${TIMESTAMP}.xml"
echo "   日志文件:  reports/e2e_china_${TIMESTAMP}.log"
