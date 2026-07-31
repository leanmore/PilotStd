#!/usr/bin/env bash
# ============================================================
# Trinity 统一门禁入口 (Single Source of Truth for Gates)
# 用法: bash scripts/check_all.sh [--fast|--deep|--docs|--all]
# ============================================================
set -euo pipefail

MODE="${1:---fast}"
EXIT_CODE=0

# --- 颜色定义 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}✅ [PASS]${NC} $1"; }
log_fail() { echo -e "${RED}❌ [FAIL]${NC} $1"; EXIT_CODE=1; }
log_warn() { echo -e "${YELLOW}⚠️  [WARN]${NC} $1"; }

# ============================================================
# --fast: 本地提交快速检查 (<10s)
# ============================================================
run_fast() {
    echo "🔍 Running FAST checks..."

    # G-010: 代码规模控制
    if python scripts/check_g_010_code_size.py; then
        log_pass "G-010 代码规模控制"
    else
        log_fail "G-010 代码规模控制"
    fi

    # G-011: 动态属性完整性
    if python scripts/check_g_011_attr_integrity.py; then
        log_pass "G-011 动态属性完整性"
    else
        log_fail "G-011 动态属性完整性"
    fi

    # G-012: SQL Schema 完整性
    if python scripts/check_g_012_sql_schema.py; then
        log_pass "G-012 SQL Schema"
    else
        log_fail "G-012 SQL Schema"
    fi

    # G-012: 注释密度
    if python scripts/check_g_012_comment_density.py; then
        log_pass "G-012 注释密度"
    else
        log_fail "G-012 注释密度"
    fi

    # 前端类型检查
    if [ -d "web" ]; then
        cd web && npx vue-tsc --noEmit 2>/dev/null && cd ..
        if [ $? -eq 0 ]; then
            log_pass "vue-tsc 类型检查"
        else
            log_fail "vue-tsc 类型检查"
        fi
    fi
}

# ============================================================
# --docs: 文档生成 + 守护 (顺序不可逆，生成失败不进入守护)
# ============================================================
run_docs() {
    echo "📄 Running DOCS pipeline (Generate → Guard)..."

    # Step 1: 生成数据文件（如果缺失）
    if [ ! -f "coverage.xml" ]; then
        echo "   ⏳ coverage.xml 不存在，正在生成..."
        python -m pytest tests/ -q --tb=short --cov=pilotstd --cov-report=xml \
            --ignore=tests/gui/ \
            --ignore=tests/test_regression_architecture.py \
            --ignore-glob="*test_ui*.py" \
            --ignore=tests/test_scan_misc.py \
            --ignore=tests/test_groups23_remaining.py \
            --ignore=tests/test_last_push.py \
            --ignore=tests/test_unified_progress.py \
            --ignore=tests/test_ci_scan_fix.py \
            -n auto 2>/dev/null || log_warn "coverage.xml 生成失败，生成器将使用降级数据"
    fi

    # Step 2: 生成器（失败则直接阻断，不进入守护）
    echo "   📊 运行 generate_status_metrics.py..."
    if python scripts/generate_status_metrics.py; then
        log_pass "generate_status_metrics.py"
    else
        log_fail "[G-032] 指标生成失败，跳过守护检查"
        exit 1
    fi

    echo "   📊 运行 generate_coverage_report.py..."
    if python scripts/generate_coverage_report.py; then
        log_pass "generate_coverage_report.py"
    else
        log_fail "[G-032] 覆盖率报告生成失败，跳过守护检查"
        exit 1
    fi

    # Step 3: 守护器
    echo "   🛡️  运行 G-032 守护器..."
    if python scripts/check_g_032_doc_health.py; then
        log_pass "G-032 文档健康度守护"
    else
        log_fail "G-032 文档健康度守护"
    fi
}

# ============================================================
# --deep: 全量静态分析 (<60s)
# ============================================================
run_deep() {
    echo "🔬 Running DEEP checks..."

    # Ruff 全量检查
    if ruff check pilotstd/ docker/ tests/ scripts/; then
        log_pass "Ruff 全量检查"
    else
        log_fail "Ruff 全量检查"
    fi

    # Mypy 类型检查
    if mypy pilotstd/ docker/ --follow-imports=skip --ignore-missing-imports; then
        log_pass "Mypy 类型检查"
    else
        log_fail "Mypy 类型检查"
    fi

    # G-020: Vulture 死代码
    if vulture pilotstd/ --min-confidence 80; then
        log_pass "G-020 Vulture 死代码"
    else
        log_fail "G-020 Vulture 死代码"
    fi

    # Schema 一致性
    if python scripts/check_schema_consistency.py; then
        log_pass "Schema 一致性"
    else
        log_fail "Schema 一致性"
    fi

    # G-037: 触发条件对齐
    if python scripts/check_g_037_trigger_alignment.py; then
        log_pass "G-037 触发条件对齐"
    else
        log_fail "G-037 触发条件对齐"
    fi

    # G-038: 历史遗留错误清零
    if python scripts/check_g_038_legacy_errors.py; then
        log_pass "G-038 历史遗留错误清零"
    else
        log_fail "G-038 历史遗留错误清零"
    fi

    # G-030: 技术债联动
    if python scripts/check_g_030_tech_debt.py; then
        log_pass "G-030 技术债联动"
    else
        log_fail "G-030 技术债联动"
    fi

    # G-033: ADR 完整性
    if python scripts/check_g_033_adr_integrity.py; then
        log_pass "G-033 ADR 完整性"
    else
        log_fail "G-033 ADR 完整性"
    fi
}

# ============================================================
# 主调度
# ============================================================
case "$MODE" in
    --fast)
        run_fast
        ;;
    --docs)
        run_docs
        ;;
    --deep)
        run_deep
        ;;
    --all)
        run_fast
        echo ""
        run_docs
        echo ""
        run_deep
        ;;
    *)
        echo "Usage: $0 [--fast|--deep|--docs|--all]"
        exit 1
        ;;
esac

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}✅ 所有检查通过！${NC}"
else
    echo -e "\n${RED}❌ 存在未通过的检查，请修复后重试。${NC}"
fi
exit $EXIT_CODE
