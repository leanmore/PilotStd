#!/usr/bin/env bash
# ============================================================
# Trinity 统一门禁入口 (Single Source of Truth for Gates)
# 用法: bash scripts/check_all.sh [--fast|--deep|--docs|--all]
# ============================================================
set -euo pipefail

# ============================================================
# 参数解析：支持叠加多个模式（如 pre-commit 的 `--fast --guards`）
#  历史缺陷：原实现只取 $1（MODE="${1:---fast}"），
#  钩子里写的 `--fast --docs` 实际只跑了 --fast，
#  导致 docs/治理类门禁从未参与提交校验（实测日志中无 docs 步骤）。
# ============================================================
MODES=()
for arg in "$@"; do
    case "$arg" in
        --fast|--docs|--deep|--guards|--local|--all) MODES+=("$arg") ;;
        *)
            echo "Usage: $0 [--fast|--docs|--deep|--guards|--local|--all] ..." >&2
            exit 1
            ;;
    esac
done
if [ ${#MODES[@]} -eq 0 ]; then
    MODES=(--fast)
fi
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

    # G-015: 相对导入有效性
    if python scripts/check_g_015_relative_imports.py; then
        log_pass "G-015 相对导入有效性"
    else
        log_fail "G-015 相对导入有效性"
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

    # G-039: 冲突标记检查（禁止 <<<<<<< / ======= / >>>>>>> 入库）
    # 起因（2026-09-26）：一次合并产生了带冲突标记的提交，却通过了当时全部门禁
    if python scripts/check_no_conflict_markers.py; then
        log_pass "G-039 冲突标记检查"
    else
        log_fail "G-039 冲突标记检查"
    fi

    # 前端类型检查（对齐 CI 的 `pnpm run type-check`，即 -p tsconfig.app.json）
    # 两个缺陷都在这一处（2026-09-26 实测）：
    # ① 必须把命令写进 if 条件：脚本开头是 set -euo pipefail，裸命令一旦返回非 0 会立刻
    #    终止整个脚本，下面的 log_fail 分支永远不可达——表现为"没有任何 FAIL 行、退出码 1"，
    #    会把"vue-tsc 工具缺失或类型错误"误报成"门禁莫名其妙挂了"。
    # ② 必须显式 -p tsconfig.app.json：web/tsconfig.json 是方案式配置（"files": [] + 仅
    #    references），不带 -p 时 vue-tsc 不检查任何文件、恒返回 0 → 这一步曾是**假绿**
    #    （注入真实 TS2322 后仍 PASS，而带 -p 立即报错），与 CI 的真检查口径不一致。
    if [ -d "web" ]; then
        if (cd web && npx vue-tsc -p tsconfig.app.json --noEmit 2>/dev/null); then
            log_pass "vue-tsc 类型检查"
        else
            log_fail "vue-tsc 类型检查"
        fi
    fi

    # G-027: Vue 组件 defineOptions（对齐 CI 的 test-frontend 步骤）
    # 2026-09-21 纳入本地：此前只在 CI 跑，新增组件漏写 defineOptions 会"本地全绿、CI 红"
    # 并连带阻断版本发布与镜像构建，代价是多跑一整轮 CI。
    if python scripts/check_g_027_define_options.py; then
        log_pass "G-027 组件 defineOptions"
    else
        log_fail "G-027 组件 defineOptions"
    fi

    # G-XXX: _wait_worker 防回潮（ADR-008）
    _wait_violations=$(grep -rn '_wait_worker' tests/ --include='*.py' \
        --exclude='helpers/__init__.py' 2>/dev/null || true)
    if [ -z "$_wait_violations" ]; then
        log_pass "G-XXX _wait_worker 防回潮"
    else
        echo "$_wait_violations"
        log_fail "G-XXX _wait_worker 防回潮 — 请使用 wait_for_worker_and_ui"
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
# --guards: 治理守护（只读、校验**入库产物**，CI 与本地共用）
#   pre-commit 钩子也跑一份作为 fail-fast，但权威执行点仍是 CI。
#   含 G-032：它同时覆盖本地产物（STATUS.md，gitignored）与入库文档
#   （coverage-report.md 等）；本地能完整校验四维度，CI 因无 STATUS.md
#   自动放行相关维度（gates.md G-032 章节已说明，属设计决策）。
#   G-038（ruff+mypy+裸 noqa）需要 PATH 上存在 ruff/mypy 可执行文件，
#   不同开发机是否安装不一致，故仍留在 --deep，不纳入提交时门禁。
# ============================================================
run_guards() {
    echo "🛡️  Running GOVERNANCE guards (read-only)..."

    # Schema 一致性
    if python scripts/check_schema_consistency.py; then
        log_pass "Schema 一致性"
    else
        log_fail "Schema 一致性"
    fi

    # G-032: 文档健康度守护（不生成，只校验）
    if python scripts/check_g_032_doc_health.py; then
        log_pass "G-032 文档健康度守护"
    else
        log_fail "G-032 文档健康度守护"
    fi

    # G-037: 触发条件对齐
    if python scripts/check_g_037_trigger_alignment.py; then
        log_pass "G-037 触发条件对齐"
    else
        log_fail "G-037 触发条件对齐"
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
# --local: 本地专属检查（输入的可靠性只存在于本地，**不得进 CI**）
#   G-031 文档联动：它比对 base..HEAD 的变更集，而本仓库以直推 main 为主，
#   CI 里该 diff 恒为空 → 只会打印"无变更文件"放行（假绿）。
#   本地则由 check_g_031_docs_sync.py 并入暂存区变更，提交前即可拦住
#   "改了代码忘了同步文档"。
# ============================================================
run_local() {
    echo "🏠 Running LOCAL-ONLY checks..."

    if python scripts/check_g_031_docs_sync.py; then
        log_pass "G-031 文档联动同步（本地）"
    else
        log_fail "G-031 文档联动同步（本地）"
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

    # G-038: 历史遗留错误清零（ruff + mypy + 裸 noqa）
    if python scripts/check_g_038_legacy_errors.py; then
        log_pass "G-038 历史遗留错误清零"
    else
        log_fail "G-038 历史遗留错误清零"
    fi

    # 治理守护（与 --guards 同一实现，避免两处漂移）
    run_guards
}

# ============================================================
# 主调度
# ============================================================
for _mode in "${MODES[@]}"; do
    case "$_mode" in
        --fast)
            run_fast
            ;;
        --docs)
            run_docs
            ;;
        --deep)
            run_deep
            ;;
        --guards)
            run_guards
            ;;
        --local)
            run_local
            ;;
        --all)
            run_fast
            echo ""
            run_docs
            echo ""
            run_deep
            ;;
    esac
done

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}✅ 所有检查通过！${NC}"
else
    echo -e "\n${RED}❌ 存在未通过的检查，请修复后重试。${NC}"
fi
exit $EXIT_CODE
