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
WITH_LINT=0
for arg in "$@"; do
    case "$arg" in
        --fast|--docs|--deep|--guards|--local|--all) MODES+=("$arg") ;;
        --with-lint) WITH_LINT=1 ;;
        *)
            echo "Usage: $0 [--fast|--docs|--deep|--guards|--local|--all] [--with-lint]" >&2
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

    # G-040: i18n 硬编码检查（组件里不得新写死中文，只拦新增）
    # 起因（2026-09-26）：SettingsTabSchedule.vue 整页 0 处 t()、文案全硬编码中文，
    # 而当时没有任何门禁能拦住——check_i18n_key_count.py 只比 locales 顶层 key，
    # 与"组件是否真的用了 i18n"无关。存量记入 scripts/i18n_hardcoded_baseline.txt，
    # 只有**超出基线**（新写死的中文）才 FAIL。
    if python scripts/check_i18n_hardcoded.py; then
        log_pass "G-040 i18n 硬编码检查"
    else
        log_fail "G-040 i18n 硬编码检查"
    fi

    # G-043: 敏感端点审计接线（凭证生命周期 / 权限与身份边界 / 不可逆批量销毁）
    # 起因（2026-09-26，第 2 批安全审计闭环）：全库仅 4 处 write_audit，而 @require_role
    # 端点有 61 处；改密、轮换静态令牌、改写通知渠道凭证这三类 P0 操作「放行不写审计」
    # 此前无门禁拦截。判定按**模块**粒度，待接入的 P1/P2 端点在脚本 EXEMPT_ROUTES
    # 显式登记（每条带理由，禁止无理由豁免）。
    if python scripts/check_sensitive_endpoint_audit.py; then
        log_pass "G-043 敏感端点审计接线"
    else
        log_fail "G-043 敏感端点审计接线"
    fi

    # G-044: 术语与禁用词检查（notification.* 文案术语一致 + 禁用词）
    # 起因（2026-09-26，第 5 批术语治理）：语言包中同一概念多译法（归档/保存、
    # 废止/作废、无法识别/未识别、未查询到/未命中）+ 技术黑话残留（适配器/堆栈）。
    # 术语唯一数据源 docs/governance/glossary.json；作用域限 notification.*
    # （界面标签用词自由度更高，全量扫描会命中"保存项目"等正确用法）。
    if python scripts/check_terminology.py; then
        log_pass "G-044 术语与禁用词检查"
    else
        log_fail "G-044 术语与禁用词检查"
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
    # T-34（2026-10-01 第十三轮 R13-2）：口径与 CI 对齐——原为 `vulture pilotstd/ --min-confidence 80`，
    # 而 CI（`.github/workflows/ci.yml`）为 `vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100`，
    # 范围少 3 个目录、阈值低 20 → `tests/` 等处的 100% 置信度死代码本地看不见（R13-1 实测：本地 --deep 全绿、CI test-backend 红）。
    if vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100; then
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
# L1/L2（T-24，2026-09-27）：ruff + mypy 快速通道
# ------------------------------------------------------------
# 起因：`scripts/update_docs.archived.py` 头部 4 行超 ruff line-length=120（E501），
# 而 ruff/mypy 只在 `--deep` 与 CI 中执行 → 本地 `--fast` 全绿、CI 连续 3 次红灯
# （run 36300484047 / 36301031251 / 36301267833），并连带 skipped 4 个 job。
# L1：`--fast` 下若**暂存变更含 .py/.pyi/.pyw**（含 scripts/ 路径），自动增跑 ruff+mypy（<5s）；
#     T-32（2026-09-27 第十二轮）：原触发式只认 `.py$`，而 G-038 的 ruff 范围**包含 .pyi**
#     → 改 `.pyi` 时本地漏检、CI 才报错，故补齐 `\.py[wi]?$`。
# L2：`--with-lint` 显式强制增跑（不依赖暂存区），供不提交时自查。
# 目标与参数与 G-038 完全一致（ruff 4 目录；mypy 仅 pilotstd/ docker/）；
# 工具缺失时**降级为 WARN 不阻断**（各机 PATH 不一致，与 G-038 不进 --fast 的既有理由一致）。
# ============================================================
run_lint_fast() {
    echo ""
    echo "🔎 L1/L2 快速 lint（ruff + mypy，T-24）..."

    local staged_relevant
    staged_relevant=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null | grep -E '^scripts/|\.py[wi]?$' || true)
    if [ "$WITH_LINT" -ne 1 ] && [ -z "$staged_relevant" ]; then
        echo "   ⏭  暂存区无 scripts/ 或 *.py/.pyi/.pyw 变更，跳过（可用 --with-lint 强制）"
        return 0
    fi
    if [ -n "$staged_relevant" ]; then
        echo "   📋 暂存 .py/.pyi/.pyw/scripts 变更：$(echo "$staged_relevant" | tr '\n' ' ')"
    fi

    if ! command -v ruff >/dev/null 2>&1; then
        log_warn "L1 ruff 未安装（pip install ruff）→ 跳过；**改 .py 的提交请改用 --deep 或先装 ruff/mypy**"
    elif ruff check pilotstd/ docker/ tests/ scripts/; then
        log_pass "L1 ruff check（4 目录，G-038 同口径）"
    else
        log_fail "L1 ruff check — 与 CI G-038 同口径，请当场修复"
    fi

    if ! command -v mypy >/dev/null 2>&1; then
        log_warn "L1 mypy 未安装（pip install mypy）→ 跳过；**改 .py 的提交请改用 --deep 或先装 ruff/mypy**"
    elif mypy pilotstd/ docker/ --follow-imports=skip --ignore-missing-imports; then
        log_pass "L1 mypy（pilotstd/ docker/，G-038 同口径）"
    else
        log_fail "L1 mypy — 与 CI G-038 同口径，请当场修复"
    fi
}

# ============================================================
# 门禁受控测试自查（R16 P0，2026-10-01）
# ------------------------------------------------------------
# 起因（技术债「`tests/` 受控测试不在本地门禁路径」）：批 6 把 G-040 存量基线清零，
# 而 tests/test_check_i18n_hardcoded.py 断言「基线文件存在」，CI test-backend 红
# （run 36293074107），本地 `--fast --guards --local` 却全绿——因为 G-040 只跑门禁脚本
# 本体，不跑它自己的受控测试。
# 处置：① `--fast` 下暂存变更命中「G-040 基线 / 其门禁脚本」时自动跑对应受控测试；
#       ② `--deep` 无条件跑一遍（CI 的 trinity-gate 会执行 `--deep`，故 CI 侧同样兜住）。
# 扩展方式：新增门禁基线时，在下方 case 里加一条「基线路径 → 受控测试」映射。
# ============================================================
run_gate_selftests() {
    local force="${1:-0}"
    echo ""
    echo "🧪 门禁受控测试自查（R16 P0）..."

    if [ "$force" -ne 1 ] && [ "$WITH_LINT" -ne 1 ]; then
        local staged_gate
        staged_gate=$(git diff --cached --name-only --diff-filter=ACMRD 2>/dev/null \
            | grep -E '^scripts/(i18n_hardcoded_baseline\.txt|check_i18n_hardcoded\.py)$' || true)
        if [ -z "$staged_gate" ]; then
            echo "   ⏭  暂存区未触及 G-040 基线/门禁脚本，跳过（--deep 会无条件跑）"
            return 0
        fi
        echo "   📋 命中门禁变更：$(echo "$staged_gate" | tr '\n' ' ')"
    fi

    if python -m pytest tests/test_check_i18n_hardcoded.py -q; then
        log_pass "门禁受控测试（G-040 基线）"
    else
        log_fail "门禁受控测试失败 — 改基线/门禁脚本后必须让对应受控测试通过"
    fi
}

# ============================================================
# 主调度
# ============================================================
for _mode in "${MODES[@]}"; do
    case "$_mode" in
        --fast)
            run_fast
            run_lint_fast
            run_gate_selftests 0
            ;;
        --docs)
            run_docs
            ;;
        --deep)
            run_deep
            run_gate_selftests 1
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
