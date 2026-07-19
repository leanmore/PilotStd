# 门禁清单（Gates）

> 本文档是 PilotStd 项目全部门禁的索引。每项门禁在 CI 的 `repo-compliance` job 中执行，失败即阻断合并。
> 
> **维护规则**：新增或修改门禁时，必须同步更新本文档。G-031 门禁会检查 `.github/workflows/` 或 `scripts/` 变更时是否更新了本文档。

---

## 门禁总览

| 编号 | 名称 | 检查内容 | 阻断条件 | 脚本路径 | 状态 |
|------|------|---------|---------|---------|------|
| G-010 | 代码规模控制 | 文件≤500行、函数≤80行 | 违规 | `scripts/check_g_010_code_size.py` | ✅ 已部署 |
| G-015 | 相对导入检查 | 所有 import 正确 | 违规 | `scripts/check_g_015_relative_imports.py` | ✅ 已部署 |
| G-016 | 动态属性完整性 | 动态属性有类型声明 | 违规 | `scripts/check_g_016_dynamic_attrs.py` | ✅ 已部署 |
| G-029 | 测试联动检查 | 改核心模块 → 测试同步更新 | 未同步 | `scripts/check_g_029_test_coverage.py` | ✅ 已部署 |
| G-030 | 技术债联动检查 | 变更模块在 known-issues.md 有记录 → 必须更新状态 | 未更新或写"待定"无计划时间 | `scripts/check_g_030_tech_debt_linkage.py` | ⏳ 待创建 |
| G-031 | 文档同步检查 | 改核心模块 → 文档同步更新 | 文档存在但未同步更新 | `scripts/check_g_031_docs_sync.py` | ⏳ 待创建 |
| G-032 | STATUS 新鲜度检查 | STATUS.md 最后修改时间 ≤ 3 天 | 超过 3 天或文件不存在 | `scripts/check_g_032_status_freshness.py` | ⏳ 待创建 |
| G-033 | ADR 完整性检查 | 新增 ADR 编号连续、历史 ADR 未被修改 | 编号不连续或历史被修改 | `scripts/check_g_033_adr_integrity.py` | ⏳ 待创建 |
| G-034 | 覆盖率阈值检查 | 整体行覆盖率 ≥ 80% | 低于 80% 或数据缺失 | `scripts/check_g_034_coverage_threshold.py` | ⏳ 待创建 |
| G-035 | 测试联动门禁 | 生产代码变更（列数/字段/API接口）时测试断言同步 | 测试中硬编码值与生产代码不一致 | 人工审查 | ⏳ 待创建 |
| G-036 | 文档联动门禁 | 变更触发文档更新规则时，对应文档必须同步变更 | 文档未更新且无合法 N/A 理由 | 人工审查 + pre-commit 提醒 | ⏳ 待创建 |
| G-037 | 触发条件对齐检查 | CLAUDE.md 触发条件表与 index.md 条目完全一致 | 存在遗漏或不一致 | `scripts/check_g_037_trigger_alignment.py` | ⏳ 待创建 |
| G-038 | 历史遗留错误清零 | 静态检查（Ruff/Mypy）发现的历史遗留错误 | 存在任何未修复的历史遗留错误 | `scripts/check_g_038_legacy_errors.py` | ⏳ 待创建 |
| repo-compliance | 入仓合规检查 | 五条入仓标准 | 违规 | `.github/scripts/check-repo-compliance.sh` | ✅ 已部署 |

---

## 门禁详细说明

### G-010：代码规模控制

- **检查内容**：Python 文件不超过 500 行，函数不超过 80 行
- **排除目录**：`.git`、`__pycache__`、`node_modules`、`dist`、`build`、`.venv`、`pilotstd_env`、`.mypy_cache`、`.pytest_cache`、`.ruff_cache`、`.qwen`、`.superpowers`、`tests`
- **阻断条件**：任一文件或函数超过阈值 → 阻断
- **执行方式**：`python scripts/check_g_010_code_size.py`

### G-015：相对导入检查

- **检查内容**：所有相对导入指向存在的模块
- **扫描范围**：`pilotstd/`、`docker/`、`web/src/` 下所有 `.py` 文件
- **阻断条件**：存在无效相对导入 → 阻断
- **执行方式**：`python scripts/check_g_015_relative_imports.py`

### G-016：动态属性完整性

- **检查内容**：动态属性赋值在 `__slots__` 中声明或使用 `@property` 装饰器
- **扫描范围**：`pilotstd/`、`docker/` 下所有 `.py` 文件
- **阻断条件**：存在未声明的动态属性 → 阻断
- **执行方式**：`python scripts/check_g_016_dynamic_attrs.py`

### G-029：测试联动检查

- **检查内容**：核心模块变更时，对应测试文件同步更新
- **映射规则**：
  - `pilotstd/core/parser.py` → `tests/test_parser.py` 或 `tests/test_scanner.py`
  - `pilotstd/query/adapters/` → `tests/test_adapters.py` 或 `tests/test_query.py`
  - `pilotstd/core/_scan.py` → `tests/test_scan.py` 或 `tests/test_scanner.py`
  - `pilotstd/ui/main_window.py` → `tests/gui/` 下任意测试文件
- **阻断条件**：核心模块变更但对应测试未同步更新 → 阻断
- **执行方式**：`python scripts/check_g_029_test_coverage.py`

### G-030：技术债联动检查

- **检查内容**：变更模块在 `known-issues.md` 有记录时，必须更新该条目状态
- **数据来源**：`docs/testing/known-issues.md` 中的"关联模块"字段
- **阻断条件**：
  - 变更涉及已登记技术债但 `known-issues.md` 未更新 → 阻断
  - 更新后状态写"待定"且无计划修复时间 → 阻断
- **执行方式**：`python scripts/check_g_030_tech_debt_linkage.py`

### G-031：文档同步检查

- **检查内容**：核心模块变更时，对应文档同步更新
- **映射规则**：
  - `pilotstd/core/parser.py` → `docs/architecture/modules/parser.md`（不存在时告警不阻断）
  - `pilotstd/query/adapters/` → `docs/architecture/modules/query.md`（不存在时告警不阻断）
  - `pilotstd/core/_scan.py` → `docs/architecture/modules/scan.md`（不存在时告警不阻断）
  - `pilotstd/ui/main_window.py` → `docs/architecture/modules/ui.md`（不存在时告警不阻断）
  - `pilotstd/manager/` → `docs/architecture/modules/manager.md`（不存在时告警不阻断）
  - `scripts/` → `docs/governance/gates.md`（存在，阻断）
  - `.github/workflows/` → `docs/governance/gates.md`（存在，阻断）
  - `docs/governance/` → `docs/governance/README.md`（存在，阻断）
  - `docs/adr/` → `docs/governance/README.md`（存在，阻断）
- **阻断条件**：文档存在但未同步更新 → 阻断；文档不存在 → 告警但不阻断
- **执行方式**：`python scripts/check_g_031_docs_sync.py`

### G-032：STATUS 新鲜度检查

- **检查内容**：`STATUS.md` 最后修改时间不超过 3 天
- **文件位置**：项目根目录 `STATUS.md`
- **阻断条件**：
  - 文件不存在 → 阻断
  - 最后修改时间超过 3 天 → 阻断
- **执行方式**：`python scripts/check_g_032_status_freshness.py`

### G-033：ADR 完整性检查

- **检查内容**：ADR 编号连续、历史 ADR 未被修改
- **扫描范围**：`docs/adr/ADR-*.md`
- **阻断条件**：
  - 编号不连续 → 阻断
  - 历史 ADR 文件被修改 → 阻断
- **执行方式**：`python scripts/check_g_033_adr_integrity.py`

### G-034：覆盖率阈值检查

- **检查内容**：整体行覆盖率 ≥ 80%
- **数据来源**：`docs/testing/coverage-report.md`
- **阻断条件**：
  - 文件不存在 → 阻断
  - 覆盖率 < 80% → 阻断
- **执行方式**：`python scripts/check_g_034_coverage_threshold.py`

### repo-compliance：入仓合规检查

- **检查内容**：五条入仓标准（白名单/黑名单/文件名模式/根目录/路径守卫）
- **数据来源**：`docs/governance/file-inclusion-criteria.md`
- **阻断条件**：任一规则违规 → 阻断
- **执行方式**：`bash .github/scripts/check-repo-compliance.sh`

### G-035：测试联动门禁

- **触发条件**：以下任一生产代码变更时触发
  1. 函数签名变更（参数增减、类型变更）
  2. 数据结构变更（INSERT 列数变更、字段新增/删除）
  3. API 接口变更（路由、参数、返回格式）
  4. 常量/枚举值变更
- **检查方式**：扫描 `tests/` 中相关测试文件，检查硬编码值/断言/常量是否与生产代码一致
- **阻断条件**：测试中存在与生产代码不一致的硬编码值 → 阻断
- **执行方式**：由执行者在提交前人工审查（后续可脚本化）
- **N/A 处理**：不涉及上述触发条件时可跳过，须在交付报告中说明原因
- **历史案例**：2026-07-18 matcher.py INSERT 从 10 列扩至 15 列，`test_announcement_matcher_full.py` 中 `len(row)` 和测试数据元组未同步更新

### G-036：文档联动门禁

- **触发条件**：参考 CLAUDE.md 第 8 节"文档联动义务"及"同步更新文档"触发规则表：
  1. API 行为变更 → `docs/architecture.md`
  2. 数据库表结构/查询逻辑变更 → `docs/architecture.md`
  3. 工具链配置变更 → `docs/development.md` 或 `docs/ci-lessons.md`
  4. 新增或修改 E2E 测试 → `docs/testing/e2e-test-manifest.md`
  5. 新增或修改 Handler/Engine 范式 → `docs/guides/*.md`
  6. 架构决策 → `docs/adr/`
  7. 门禁规则新增/修改 → `docs/governance/gates.md`
- **检查方式**：提交前检查本次修改是否触发上述规则，确认对应文档是否有变更
- **阻断条件**：触发规则但对应文档未更新且无合法 N/A 理由 → 阻断
- **执行方式**：由 pre-commit hook 输出文档联动提醒（不阻断），CI 中由 G-031 阻断
- **N/A 处理**：允许 N/A，须写明原因（如"仅修改内部实现，对外接口不变"）
- **与 G-031 的关系**：G-031 是自动化执行脚本，G-036 是规则定义。G-036 定义"何时需要更新文档"，G-031 执行检查

### G-037：触发条件对齐检查

- **检查内容**：比对 `CLAUDE.md` 中的"读文档触发条件表"与 `docs/index.md` 中的文档索引条目。
- **阻断条件**：任一文档在 `CLAUDE.md` 中有触发条件但 `index.md` 中缺失，或反之 → 阻断。
- **执行方式**：`python scripts/check_g_037_trigger_alignment.py`

### G-038：历史遗留错误清零

- **检查内容**：运行 Ruff 和 Mypy 静态检查，扫描项目全量代码。
- **阻断条件**：发现任何历史遗留的 lint 或类型错误 → 阻断。禁止使用 `# noqa` 或 `--add-noqa` 静默历史错误。执行者必须当场修复代码，确保零错误后方可继续提交流程。
- **执行方式**：`python scripts/check_g_038_legacy_errors.py`

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.2 | 2026-07-19 | 新增 G-037（触发条件对齐）、G-038（历史遗留错误清零） |
| v1.1 | 2026-07-18 | 新增 G-035（测试联动）、G-036（文档联动） |
| v1.0 | 2026-07-14 | 初始版本，收录 10 项门禁 |
