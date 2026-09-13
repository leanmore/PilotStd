# 门禁清单（Gates）

> 本文档是 PilotStd 项目全部门禁的索引。每项门禁在 CI 的 `repo-compliance` job 中执行，失败即阻断合并。
>
> **维护规则**：新增或修改门禁时，必须同步更新本文档。G-031 门禁会检查 `.github/workflows/` 或 `scripts/` 变更时是否更新了本文档。

---

## 门禁总览

| 编号 | 名称 | 检查内容 | 阻断条件 | 脚本路径 | 状态 |
|------|------|---------|---------|---------|------|
| G-010 | 代码规模控制 | 文件有效代码行≤500行（>400警告）、函数≤80行；>500行阻断时须提供拆分证据 | 文件>500行/函数>80行（拆分证据不足亦阻断） | `scripts/check_g_010_code_size.py` | ✅ 已部署 |
| G-015 | 相对导入检查 | 所有 import 正确 | 违规 | `scripts/check_g_015_relative_imports.py` | ✅ 已部署 |
| G-029 | 测试联动检查 | 改核心模块 → 测试同步更新 | 未同步 | `scripts/check_g_029_test_coverage.py` | ✅ 已部署 |
| G-030 | 技术债联动检查 | 新增 `# TECH-DEBT:` / `# TODO(debt):` 标记必须同步技术债登记簿 | 新增标记但登记簿未同步 | `scripts/check_g_030_tech_debt.py` | ✅ 已部署 |
| G-031 | 文档同步检查 | 改核心模块 → 文档同步更新 | 文档存在但未同步更新 | `scripts/check_g_031_docs_sync.py` | ⏳ 待创建 |
| G-032 | 文档健康度守护 | 生成器存活 / 人工层新鲜度 / 交叉引用完整 / 数据源唯一性 四维度 | 任一维度违规 | `scripts/check_g_032_doc_health.py` | ✅ 已部署 |
| G-033 | ADR 完整性检查 | 架构变更须有有效 ADR（非 proposed/draft） | 架构变更但无有效 ADR | `scripts/check_g_033_adr_integrity.py` | ✅ 已部署 |
| G-034 | 覆盖率阈值检查 | 整体行覆盖率 ≥ 80% | 低于 80% 或数据缺失 | `scripts/check_g_034_coverage_threshold.py` | ⏳ 待创建 |
| G-035 | 测试联动门禁 | 生产代码变更（列数/字段/API接口）时测试断言同步 | 测试中硬编码值与生产代码不一致 | 人工审查 | ⏳ 待创建 |
| G-036 | 文档联动门禁 | 变更触发文档更新规则时，对应文档必须同步变更 | 文档未更新且无合法 N/A 理由 | 人工审查 + pre-commit 提醒 | ⏳ 待创建 |
| G-037 | 触发条件对齐检查 | AGENTS.md 触发条件表与 index.md 条目完全一致 | 存在遗漏或不一致 | `scripts/check_g_037_trigger_alignment.py` | ✅ 已部署 |
| G-038 | 历史遗留错误清零 | 静态检查（Ruff/Mypy）发现的历史遗留错误 | 存在任何未修复的历史遗留错误 | `scripts/check_g_038_legacy_errors.py` | ✅ 已部署 |
| repo-compliance | 入仓合规检查 | 五条入仓标准 | 违规 | `.github/scripts/check-repo-compliance.sh` | ✅ 已部署 |

---

## 门禁详细说明

### G-010：代码规模控制

- **检查内容**：Python 文件不超过 500 行，函数不超过 80 行
- **排除目录**：`.git`、`__pycache__`、`node_modules`、`dist`、`build`、`.venv`、`pilotstd_env`、`.mypy_cache`、`.pytest_cache`、`.ruff_cache`、`.qwen`、`.superpowers`、`tests`
- **两档制**：
  - ⚠️ 警告档：文件有效代码行 >400 且 ≤500 → 输出 warning，不强制拆分
  - 🔴 阻断档：文件有效代码行 >500 → 输出 error，exit 1，并要求拆分验证
- **阻断解除条件**（v2，同时满足，缺一不可）：
  1. **拆分证据存在**：同目录下存在 `{原文件名}/` 子目录 **或** `{原文件名}_*.py` 模块文件
  2. **原文件 ≤500 行**：原文件的有效代码行 ≤500
- **拆分证据不校验质量**：空模块/占位文件也视为证据，拆分质量由 PR Review 把关
- **执行方式**：`python scripts/check_g_010_code_size.py`

### G-015：相对导入检查

- **检查内容**：所有相对导入指向存在的模块
- **扫描范围**：`pilotstd/`、`docker/`、`web/src/` 下所有 `.py` 文件（`pilotstd/templates/` 模板目录除外；`docker/` 按 PEP 420 命名空间包处理）
- **阻断条件**：存在未受 try/except 保护的无效相对导入 → 阻断（try/except 保护的失效导入仅警告，视为有意的可选依赖回退）
- **执行方式**：`python scripts/check_g_015_relative_imports.py`（已接入 `check_all.sh --fast` 与 ci.yml repo-compliance job）

### G-029：测试联动检查

- **检查内容**：核心模块变更时，对应测试文件同步更新
- **映射规则**：
  - `pilotstd/announcement/parser.py` → `tests/test_parser.py` 或 `tests/test_scanner.py`
  - `pilotstd/query/adapters/` → `tests/test_adapters.py` 或 `tests/test_query.py`
  - `pilotstd/manager/facade/_scan.py` → `tests/gui/test_scan.py` 或 `tests/test_scanner.py`
  - `pilotstd/ui/main_window/` → `tests/gui/` 下任意测试文件
- **阻断条件**：核心模块变更但对应测试未同步更新 → 阻断
- **执行方式**：`python scripts/check_g_029_test_coverage.py`

### G-030：技术债联动检查

- **检查内容**：检测本次变更中**新增**的 `# TECH-DEBT:` / `# TODO(debt):` 标记（仅增量，忽略存量与文档文件）
- **联动要求**：新增标记的同次提交必须包含技术债登记簿（`docs/architecture/technical-debt-registry.md` 或 `docs/technical-debt.md`）的变更
- **阻断条件**：检测到新增标记但登记簿未同步变更 → 阻断
- **执行方式**：`python scripts/check_g_030_tech_debt.py`（ci.yml repo-compliance job 部署）

### G-031：文档同步检查

- **检查内容**：核心模块变更时，对应文档同步更新
- **映射规则**：
  - `pilotstd/announcement/parser.py` → `docs/architecture/modules/parser.md`（不存在时告警不阻断）
  - `pilotstd/query/adapters/` → `docs/architecture/modules/query.md`（不存在时告警不阻断）
  - `pilotstd/manager/facade/_scan.py` → `docs/architecture/modules/scan.md`（不存在时告警不阻断）
  - `pilotstd/ui/main_window/` → `docs/architecture/modules/ui.md`（不存在时告警不阻断）
  - `pilotstd/manager/` → `docs/architecture/modules/manager.md`（不存在时告警不阻断）
  - `scripts/` → `docs/governance/gates.md`（存在，阻断）
  - `.github/workflows/` → `docs/governance/gates.md`（存在，阻断）
  - `docs/governance/` → `docs/governance/README.md`（存在，阻断）
  - `docs/adr/` → `docs/governance/README.md`（存在，阻断）
- **阻断条件**：文档存在但未同步更新 → 阻断；文档不存在 → 告警但不阻断
- **执行方式**：`python scripts/check_g_031_docs_sync.py`

### G-032：文档健康度守护

- **检查内容**：四维度守护
  1. 生成器存活：STATUS.md / coverage-report.md 的 AUTO-GENERATED 标记与时间戳（无标记首跑赦免）
  2. 人工层新鲜度：人工维护文档按类别分级检查最后修改时间（30/60 天宽限期）
  3. 交叉引用完整性：文档引用的文件路径存在性
  4. 数据源唯一性：STATUS.md 人工区禁止裸覆盖率/测试数（可标记 `[legacy-manual]` 豁免）
- **阻断条件**：任一维度错误（警告不阻断）
- **执行方式**：`python scripts/check_g_032_doc_health.py`（ci.yml repo-compliance job 部署）

> **CI 环境行为说明**：
>
> 本门禁在 CI 环境（GitHub Actions）中的校验强度低于本地环境，原因如下：
> - `STATUS.md` 设计为**本地状态文件，不入仓库**（文件头自述"本地状态文件，不入仓库"，见仓库根目录 `STATUS.md`）
> - CI 全新检出时没有 `STATUS.md` 文件，因此该门禁的维度1（STATUS.md 标记新鲜度）和维度4（STATUS.md 人工区完整）自动放行（缺失即警告）
> - CI 中实际生效的是：`coverage-report.md` 的标记新鲜度 + 人工层新鲜度 + 交叉引用等
>
> 这是**设计决策**，非功能缺陷。如需在 CI 中获得完整校验，需改变 `STATUS.md` 的设计（纳入版本控制），此决策不在当前范围。

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

- **触发条件**：参考 AGENTS.md R-004（联动改）及"同步更新文档"触发规则表：
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

### G-037：文档生命周期对齐检查

- **检查内容**：三维度守护——① 读取侧双向对齐：比对 `AGENTS.md` 8.1"读文档触发条件表"与 `docs/index.md` 文档索引条目；② 回写侧存在性：`AGENTS.md` 8.2 回写清单列出的文档物理存在；③ 回写侧覆盖完整性：8.1 中标记为「代码说明书」的文档与 8.2 回写清单完全一致。
- **阻断条件**：任一维度违规 → 阻断（索引遗漏 / 回写文档缺失 / 代码说明书漏同步）。
- **执行方式**：`python scripts/check_g_037_trigger_alignment.py`

### G-038：历史遗留错误清零

- **检查内容**：运行 Ruff 和 Mypy 静态检查，扫描项目全量代码。
- **阻断条件**：发现任何历史遗留的 lint 或类型错误 → 阻断。禁止使用 `# noqa` 或 `--add-noqa` 静默历史错误。执行者必须当场修复代码，确保零错误后方可继续提交流程。
- **CI 门禁**：`ci.yml` test-backend job 中运行 `ruff check pilotstd/ docker/ tests/ scripts/ --output-format=github`，位于后端测试之前（fail-fast），失败即阻断 PR。
- **基线**：0 errors（2026-08-14，commit `594ab8f2`）。
- **策略**：零容忍，任何新增的 lint 错误（F841/E501/E702/F401/I001 等）直接在 PR 阶段被 CI 拦截。
- **执行方式**：`python scripts/check_g_038_legacy_errors.py`

---

## 执行入口：`scripts/check_all.sh` 模式

| 模式 | 内容 | 是否写文件 |
|------|------|-----------|
| `--fast` | G-010 代码规模、G-011 动态属性、G-015 相对导入、G-012 SQL Schema/注释密度、vue-tsc、`_wait_worker` 防回潮 | 否 |
| `--guards` | **治理守护（只读）**：Schema 一致性、**G-032 文档健康度**、G-037、G-030、G-033、**G-031 文档联动同步** | 否 |
| `--docs` | coverage.xml（缺失时生成）→ `generate_status_metrics.py` → `generate_coverage_report.py` → G-032 守护 | **是**（重写 `STATUS.md`、`docs/testing/coverage-report.md`） |
| `--deep` | Ruff 全量、Mypy、G-020 Vulture、G-038、`--guards` | 否 |
| `--all` | `--fast` → `--docs` → `--deep` | 是 |

### 生成与守护的分工（2026-09-13 明确）

| 环节 | 在哪执行 | 守护什么 |
|------|---------|---------|
| **文档生成** | **仅本地**：`bash scripts/check_all.sh --docs` | — （产物 `STATUS.md` 为 gitignored 本地文件；`docs/testing/coverage-report.md`、`docs/governance/capabilities_registry.md` 入库，人工确认后提交） |
| **守护本地产物 / 本地编辑纪律** | **本地 pre-commit**（`--fast --guards`，含 G-032、G-031） | 只有本机同时具备 `STATUS.md` 与刚生成的覆盖率报告，G-032 四维度才能完整校验；G-031 在提交前提醒"改了代码要同步改文档"（含暂存区变更） |
| **守护入库文档** | **CI**（`ci.yml` repo-compliance：`check_g_032_doc_health.py`、`check_docs_sync.py`、`check_capabilities_sync.py`；`trinity-gate.yml` 的 `--deep`） | 入库文档的新鲜度分档（7/30/60 天）、交叉引用完整性、模块文档与代码的联动、能力矩阵与代码是否一致；`STATUS.md` 因不入库，相关维度在 CI 自动放行 |

- **多模式可叠加**：`check_all.sh --fast --guards` 会依次执行两个模式（2026-09-13 修复：
  原实现 `MODE="${1:---fast}"` 只取第一个参数，导致 pre-commit 钩子里写的
  `--fast --docs` 实际只跑 `--fast`，docs 类门禁形同虚设；未知参数现在直接报用法并退出 1）。
- **pre-commit 钩子**（`.husky/pre-commit`）执行 `--fast --guards`：选用 `--guards` 而非 `--docs`，
  因为生成属本地行为、且 `--docs` 会重写工作树文件并重跑带覆盖率采集的 pytest。
- **CI 不生成文档**：`trinity-gate.yml` 执行 `--deep`（不再带 `--docs`），已移除原先空转的
  pytest 采集与 artifact 上传步骤。
- **G-038 仍在 `--deep`**：它需要 PATH 上存在 `ruff`/`mypy` 可执行文件，各开发机是否安装不一致，
  故不纳入提交时门禁；CI 的 test-backend job 用 venv 内的 ruff 强制执行。
- **G-031 的放置（2026-09-13 定案）**：`check_g_031_docs_sync.py`（9 条映射，比 CI 现有的
  `check_docs_sync.py` 多覆盖 `scripts/`、`.github/workflows/`、`docs/governance/`、
  `docs/architecture/decisions/`）**放在本地**——它约束的是"改了代码要同步改文档"这一**本地编辑动作**，
  提交前就该提醒作者；为此该脚本已并入暂存区变更（`git diff --cached`），
  否则 pre-commit 时"正要提交的这次改动"尚未进入 HEAD，门禁会空转。
  CI 侧继续由 `check_docs_sync.py` 校验**入库**文档，两者互补、规则集不同。
- **能力矩阵同步的放置（2026-09-13 定案）**：`docs/governance/capabilities_registry.md`
  是**入库**文档，故其"与代码是否一致"的校验放在 **CI**：
  `scripts/check_capabilities_sync.py`（重生成 → 忽略时间戳行比对 → 还原文件 → 结论），
  已接入 `ci.yml` repo-compliance job。生成动作仍在本地，
  由 AGENTS.md 第七节要求人工重跑并一并提交。

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.7 | 2026-09-13 | 按"检查跟随产物位置"定案两处放置：G-031 放**本地**（并入暂存区变更，提交前即生效；CI 侧保留 `check_docs_sync.py` 校验入库文档）；能力矩阵同步放 **CI**（新增 `scripts/check_capabilities_sync.py` 并接入 repo-compliance，重生成后忽略时间戳行比对入库内容）；「生成与守护的分工」表随之更新 |
| v1.6 | 2026-09-13 | 明确"生成在本地、守护分两处"的分工；G-032 纳入 `--guards`（本地守护本地产物，CI 复用同一实现守护入库文档）；`trinity-gate.yml` 改回 `--deep`（CI 不生成、不上传 artifact），清理空转步骤；登记 G-031 与 capabilities_registry 同步两处缺口 |
| v1.5 | 2026-09-13 | 修复 `check_all.sh` 参数解析（支持多模式叠加，未知参数报错退出）；新增 `--guards` 只读治理守护模式并接入 pre-commit 钩子（原 `--fast --docs` 的 docs 部分从未执行）；补充"执行入口"章节 |
| v1.4 | 2026-08-24 | G-010 升级 v2：>500 行阻断新增拆分验证（拆分证据 + 原文件 ≤500 行，缺一不可）；警告档（400-500 行）行为不变 |
| v1.3 | 2026-08-20 | 移除 G-016（与 G-011 重复）；补齐 G-015 脚本并接入 `check_all.sh --fast`；G-032 补充 CI 行为说明 |
| v1.2 | 2026-07-19 | 新增 G-037（触发条件对齐）、G-038（历史遗留错误清零） |
| v1.1 | 2026-07-18 | 新增 G-035（测试联动）、G-036（文档联动） |
| v1.0 | 2026-07-14 | 初始版本，收录 10 项门禁 |
