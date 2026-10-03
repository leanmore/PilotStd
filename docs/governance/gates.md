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
| G-027 | Vue 组件 `defineOptions` 检查 | `web/src/{components,views}` 下所有 `<script setup>` 组件必须声明 `defineOptions` | 缺失 | `scripts/check_g_027_define_options.py` | ✅ 已部署（CI + 本地 `--fast`） |
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
| G-039 | 冲突标记检查 | 提交/入库内容不得含 `<<<<<<<` / `=======` / `>>>>>>>` 合并冲突标记 | 命中冲突块或孤立标记 | `scripts/check_no_conflict_markers.py` | ✅ 已部署 |
| G-040 | i18n 硬编码检查 | `web/src/**/*.{vue,ts}` 里不得**新增**写死的中文文案（注释除外；存量走基线） | 超出 `scripts/i18n_hardcoded_baseline.txt` 的行数 | `scripts/check_i18n_hardcoded.py` | ✅ 已部署 |
| G-043 | 敏感端点审计接线 | `docker/api/**/*.py` 中命中敏感清单（S1 凭证生命周期 / S2 权限与身份边界 / S3 不可逆批量销毁）的状态变更端点必须有 `write_audit` | 敏感路由所属模块内无 `write_audit` 调用 | `scripts/check_sensitive_endpoint_audit.py` | ✅ 已部署 |
| G-044 | 术语与禁用词检查 | `notification.*` 作用域内的文案不得命中术语表的 `forbidden` 词组；术语表 `keys` 登记的键三语值必须与登记值严格相等 | 命中禁用词，或术语三语不一致 | `scripts/check_terminology.py` | ✅ 已部署 |
| G-045 | 通知系统覆盖度基线 | 每个已注册事件必须：i18n 三语键齐备、出现在 e2e `EVENTS` 且其 `trigger_file` 物理存在、安全类事件触发文件含 `write_audit` | 任一维度缺失（术语登记为跟踪项，`--strict` 才升阻断） | `scripts/audit_notification_coverage.py` | ✅ 已部署 |
| G-046 | 通知链路审计 | 通知构建器不得出现空文本风险、不得缺空值守卫、不得静默吞错 | 任一发现（`--strict`，零基线） | `scripts/audit_notification_chain.py` | ✅ 已部署 |
| G-047 | Python 侧 i18n 硬编码检查 | `pilotstd/`、`docker/` 的 **Python 字符串字面量**中不得**新增**写死的中文（**跳过 docstring**——G-012 强制其中文；注释不在 AST 中不计） | 超出 `scripts/i18n_hardcoded_python_baseline.json` 的新增 | `scripts/check_i18n_hardcoded_python.py` | ✅ 已部署 |
| G-048 | 架构文档模块计数一致性 | `docs/architecture/modules/core.md` 的「子模块数」必须等于 `pilotstd/core/` 递归全部 `.py` 数（含 `__init__.py`，不含 `__pycache__`） | 文档数字与实际文件数不符 | `scripts/check_g_048_core_module_count.py` | ✅ 已部署 |
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
- **联动要求**：新增标记的同次提交必须包含技术债登记簿（`docs/technical-debt.md`，唯一数据源；旧簿已于 2026-09-27 废止归档）的变更
- **阻断条件**：检测到新增标记但登记簿未同步变更 → 阻断
- **执行方式**：`python scripts/check_g_030_tech_debt.py`（ci.yml repo-compliance job 部署）

### G-031：文档同步检查

- **检查内容**：核心模块变更时，对应文档同步更新
- **事实归属判据**（本条门禁的设计依据）：文档是代码的另一层简写，唯一价值是与代码一致。因此只问一句——**这次变更改变了哪个事实？承载那个事实的是哪份文档？** 是则必须同批同步，不是则门禁不该管。据此，每个变更文件按**最长匹配前缀**归属**唯一**目标文档（一份事实只由一份文档承载），避免"改了 `pilotstd/scan/parser/` 还要顺带碰 `scan.md`"这类形式联动。
- **映射规则**（与 `scripts/check_g_031_docs_sync.py` 的 `DOC_SYNC_MAP` 逐条对应；源前缀必须是仓库内真实存在的路径，否则该条永不触发 = 死映射/门禁假绿；目标文档必须是承载该源路径事实的那一份）：
  - `pilotstd/scan/parser/` → `docs/architecture/modules/parser.md`（parser.md 自述模块路径即此，核心类 `StandardParser`）
  - `pilotstd/query/adapters/` → `docs/architecture/modules/query.md`
  - `pilotstd/scan/` → `docs/architecture/modules/scan.md`（scan.md 自述模块路径即此）
  - `pilotstd/ui/main_window/` → `docs/architecture/modules/ui.md`
  - `pilotstd/manager/` → `docs/architecture/modules/manager.md`（`manager/facade/_scan.py` 属此，不再牵连 scan.md）
  - `pilotstd/core/` → `docs/architecture/modules/core.md`（**2026-09-25 补入**，原为已知缺口：core.md 自述"G-031 映射 `pilotstd/core/`"却不在表里，改任何 core 文件都不触发同步）
  - `pilotstd/announcement/` → `docs/reference/announcement-pipeline.md`（**2026-09-25 补入**，该文档即 AGENTS.md §八 8.2 指定的回写目标）
  - `pilotstd/download/` → `docs/reference/download-pipeline.md`（**2026-09-26 补入**，技术债 #24：该目录此前不在表里，改下载适配器不触发任何文档同步——#21 的三处流程变化只写进了代码 docstring；新建的 download-pipeline.md 承载 hcno 权威来源 / 端点族 `/bzgk/std/*` / 步骤链 / 历史事故 / 防回归测试清单）
  - `scripts/` → `docs/governance/gates.md`
  - `.github/workflows/` → `docs/governance/gates.md`
  - `docs/governance/` → `docs/governance/README.md`
  - `docs/adr/` → `docs/adr/README.md`（**仅新增/删除/重命名**时要求同步：改 ADR 正文只影响该 ADR 自身，"有哪些决策"这份清单并未变化）
- **已知缺口**：无（2026-09-25 起原两条缺口已补；2026-09-26 再补第三条；映射共 **12 条**，自检脚本可验证"源前缀与目标文档均存在"，确保无死映射）
- **机器生成产物豁免**：`docs/governance/capabilities_registry.md`（由 `scripts/generate_capabilities.py` 生成，且已登记在 `docs/governance/README.md` 索引中）**单独**变更时不要求同步 README —— 重生成只改时间戳/行号，不改变索引语义；AGENTS.md §七 又强制其随 `pilotstd/core/`、`docker/api/` 变更一并提交，若不豁免，则每次重生成都会撞上本条规则，只能做装饰性改动或绕过门禁。同批若还含 `docs/governance/` 下的人工文档变更，仍按上表阻断；豁免命中时输出 `[G-031] SKIP: ...`，不静默跳过
- **阻断条件**：目标文档存在但未同步更新 → 阻断；目标文档不存在 → 按模式处理，`block` 同样阻断、`warn` 仅告警（当前 12 条均为 `block`，且 12 个目标文档均已存在）
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

### G-039：冲突标记检查

**检查内容**：禁止把合并冲突标记提交入库——命中「一行以 7 个 `<` 开头且其后存在一行以 7 个 `>` 开头」的**冲突块**，
或**孤立**的 `<`/`>` 标记行，即阻断。块内以 7 个 `=` 开头的行一并报告（`=======` 在 Markdown 里是合法的 Setext 标题下划线，
**只在成块时**才算违规，避免误伤）。

**扫描范围**（优先级）：显式路径参数 > 暂存区（`git diff --cached`，pre-commit 场景）> 全库已跟踪文件（`git ls-files`，CI 场景）。
**排除**：`.gitignore` 忽略的文件；`WHITELIST_NAME_SUFFIXES`（仅限“用于测试本门禁自身”的 fixture 文件名）。

**起因**（2026-09-26）：一次多分支合并中，解析脚本断言失败后同一条命令里的 `git add` + `git commit` 仍然执行，
产生了**带冲突标记的合并提交**，而它通过了当时 pre-commit 的**全部**门禁——在此之前没有任何机制能拦住这类提交。

**执行方式**：`python scripts/check_no_conflict_markers.py`（已在 `check_all.sh --fast` 与 CI `repo-compliance` 接入）；
受控测试：`tests/test_check_no_conflict_markers.py`（8 例：正常文件 / 冲突块 / 孤立标记 / Setext 下划线不误伤 / 白名单 / CLI 退出码 / 自扫描 / 二进制跳过）。

---

### G-040：i18n 硬编码检查

**检查内容**：扫描 `web/src/**/*.vue`、`web/src/**/*.ts`，去掉注释后若某行出现**中日韩统一表意文字**
（U+3400–U+9FFF、U+F900–U+FAFF），即记一处；只有**超出基线**的部分才阻断。输出格式为 `文件:行号: 片段`。

**排除**：`*.test.ts` / `*.spec.ts` / `*.d.ts`、`web/src/locales/`（语言包本体）、`node_modules`、`dist`。
**豁免**：① 注释（**行首与行尾** `//`、`/* */`、`<!-- -->` 都不计）；② 行内标记 `i18n-allow`——本行或上一行含该注释即跳过
（用于与后端中文状态值比较、开发日志、审计元数据等确不需翻译的文案）；③ 存量基线；
④ **路径级豁免**（仅精确路径，不按前缀/通配）：`EXCLUDE_FILES`=语言包本体（如 `web/src/lib/primevueLocale.ts`，
文件内已含三语，属本地化数据）。（v1.23 曾并存 `EXEMPT_DEAD_CODE`=死代码豁免；该批死代码已于 v1.24 删除，豁免随之取消。）

**注释识别口径**（v1.23 起）：改为**字符串状态机**逐字符判定——只有"知道自己在不在字符串里"才能区分
`'#065f46', // 深绿…`（真行尾注释 → 抹掉）与 `'https://x/y 中文'`（字符串内的 `//` → 不截断）。
`tokenize` 只适用于 Python 源码（本门禁扫 `.vue`/`.ts`），纯正则无法可靠判定引号配对。单/双引号串按 JS 语义
**不跨行**（遇换行复位），反引号模板串允许跨行。同一处修复还消除了旧 `/*…*/` 正则的**漏报**：`accept="image/*"`
里的 `/*` 会与后面任意 `*/` 配对、把中间整段真实文案抹平（实测漏掉 3 行）。

**存量基线**：`scripts/i18n_hardcoded_baseline.txt`，格式 `<相对路径>::<行数>`。设计原则是**只拦新增**：
- 文件不在基线里且有中文 → 全部算违规（新文件必须一开始就走 i18n）；
- 文件在基线里但**行数变多** → 只报多出来的行（同一文件里新写死的中文照样拦得住）；
- 文件在基线里但行数变少 → 只打印 `[STALE]` 提示（不阻断），可跑 `--update-baseline` 收紧基线。

**起因**（2026-09-26）：`web/src/views/settings/SettingsTabSchedule.vue` 整页 0 处 `useI18n` / `t()`，
文案全是硬编码中文（用户切到 en 界面仍是中文），而当时**没有任何门禁**能拦住——`check_i18n_key_count.py`
只比对 locales 的顶层 key，与“组件是否真的用了 i18n”无关。同一轮还发现三语存在 9 个叶子键漂移
（zh-CN 缺 5 个 `nav.*`、zh-TW/en 各缺 4 个 `home.*`），遂把该脚本升级到 v1.1.0 增加**叶子键路径**对齐检查。

**执行方式**：`python scripts/check_i18n_hardcoded.py`（`check_all.sh --fast` 与 CI `test-frontend` 步骤均已接入）；
辅助模式：`--report`（存量排行，供专项清理排期）、`--update-baseline`（偿还后收紧基线）、`<file|dir>`（只扫指定目标）。
受控测试：`tests/test_check_i18n_hardcoded.py`（**19 例**：干净文件 / 模板硬编码 / 脚本硬编码 / 三类注释 /
`https://` 不误判 / **尾随 `//` 注释不报** / **字符串内 `//` 仍报** / **`/*` 不再吞代码** /
`i18n-allow` 行内与上一行 / 排除规则 / **路径级豁免生效且不波及其它文件** / 基线内通过 / 只报超出部分 /
基线过期不阻断 / 更新基线 / report 不判失败 / 仓库自检）。

**存量（B0 前置清理后，2026-09-27）**：基线 **897 行/76 文件 → 786 行/61 文件**（−111）。分解：
① 注释口径修复 −48 行（行尾 `//` 误报，19 个文件）+3 行（旧 `/*…*/` 正则漏报，`SettingsTabAppearanceMixed.vue`）；
② 路径豁免 −43 行/3 文件（语言包 16 + 死代码 27）；③ `i18n-allow` −23 行（后端中文状态值 9 + 开发日志 12 + 审计元数据 2）。

**存量（v1.24 删除死代码后）**：门禁口径**仍为 786 行/61 文件**——被豁免的 3 个文件从不进基线，删掉其中 2 个自然不改变基线；
但**源码里的中文实际减少 27 行**（`types/dashboard.ts` 24 + `constants/sourceMapping.ts` 的 `SOURCE_LABEL` 3），
即按「含豁免文件」计的真实存量 829 → **802** 行（语言包本体 16 行仍在）。

**存量（批 1 通知域 i18n 化后，2026-09-27）**：基线 **786 行/61 文件 → 627 行/57 文件**（−159）。本批清零 4 个文件（A 类文案全部改走 `t()`）：
`NotificationConfig.vue` 77→0、`NotificationLogsView.vue` 72→0、`NotificationBell.vue` 8→0、`settings/SettingsTabNotification.vue` 2→0；
三语新增 `notification.*` 命名空间 **175 行/文件**（叶子键 129 → 307）。

**存量（批 2 设置页 i18n 化 + 事件名统一后，2026-09-27）**：基线 **627 行/57 文件 → 388 行/43 文件**（−239，实测值；阶段 1 报告预估 229）。
清零 14 个文件：`SettingsTabUsers` 30、`SettingsTabToken` 19、`SettingsTabValidity` 16、`SettingsTabCircuit` 15、`SettingsTabSystem` 2、
`SettingsView` 11、`ValidityConfig` 54、`WechatTrustIP` 45（第 46 行 `current_ip !== '未知'` 属 C-2，按决策 2 只豁免）、
`FileMonitor` 17、`CacheManager` 11、`SettingsTabSchema` 5、`SettingsTabAppearanceMixed` 7、`DynamicSettingField` 2、`config/themes.ts` 4。
三语 `settings.*` 扩展 + `common.yes/no`，叶子键 **307 → 471**；事件名合并为单一 `notification.event.*`（36 项，取配置页措辞，删除 `config.event`/`logs.event` 两套，叶子键 307→272 后并入本批）。

**存量（批 3 任务/下载/整理 i18n 化 + settings.tasks 键迁移后，2026-09-27）**：基线 **388 行/43 文件 → 248 行/35 文件**（−140，实测值；阶段 1 报告预估 136）。
清零 8 个文件：`TaskView` 42、`TaskManager` 35、`DownloadImport` 15、`OrganizeView` 14、`PendingView` 11（第 60-62 行 C-2 状态值按决策 2 保持 `i18n-allow` 不动）、
`QualityView` 10、`SchedulerStatus` 9、`DownloadQueue` 4。三语扩展 `task.*`（含 `task.manager.*`）/`organize.*`/`quality.*`/`scheduler.*`/`download.manual_import.*`/`download.queue.*` + `pending.*` 补 9 键，
叶子键 **469 → 612**；另把 `settings.tasks.save/saved` 迁移到批 2 建的通用键 `settings.save_config/saved` 并删除重复（叶子键 471 → 469）。

**存量（批 4 公告/标准状态 i18n 化后，2026-09-27）**：基线 **248 行/35 文件 → 176 行/31 文件**（−72，实测值；阶段 1 报告预估 67）。
清零 4 个文件：`StandardsStatusView` 24（其中 3 行 filter `value` 属 C-2 后端中文状态值，按决策 2 加 `i18n-allow`；另 3 行既有豁免未动）、
`AnnounceDetail` 20、`composables/useAnnounceDetail` 18、`AnnounceView` 10。三语新增 `announce.view.*` / `announce.detail.*`（含 `parse_status`/`record_status`/`toast` 子表）+ 新顶层 `standards.*`，
叶子键 **612 → 694**（静态 70 + 动态拼接 12）。**新增 `web/src/i18n.ts`**：把全局 i18n 实例从 `main.ts` 抽出（`main.ts` 有效行 123 → 107，注册/语言切换行为不变），供 composable 等非组件模块用 `i18n.global.t`。

**存量（批 5 仪表板/布局 i18n 化后，2026-09-27）**：基线 **176 行/31 文件 → 83 行/16 文件**（−93，实测值；阶段 1 报告预估 88）。
清零 15 个文件：`AppLayout` 7、`AppHeader` 4、`AppSidebar` 2、`composables/useDashboard` 9、9 个 widget（`AdapterStatusCard` 11 / `AdapterStatusAnnounceCard` 9 / `QuickActionsCard` 9 /
`SystemInfoCard` 9 / `TaskTrendCard` 8 / `SystemLogCard` 7 / `AdapterStatusQueryCard` 5 / `RecentAnnounceCard` 6 / `PendingItemsCard` 4）+ `PlaceholderWidget` 2 + `StatsCard` 1。
三语新增顶层 `dashboard.*`（`common`/`card`/`layout`/`header`/`sidebar`/`adapter`/`announce_adapter`/`query_adapter`/`quick_actions`/`sys_info`/`trend`/`sys_log`/`recent_announce`/`pending`/`placeholder`/`stats`），
叶子键 **694 → 772**（静态 68 + 表驱动 10）。**模块级表按 `labelKey` 机制改**：`useDashboard.ts` 的 `CARD_REGISTRY.label/zhName` → **`labelKey`/`titleKey`**（渲染端 `t()`），消费方 `AppLayout`（`t(card.labelKey)`）/`HomeView`（`:title-key`）/`AdapterStatusQueryCard`（`props.titleKey`）同批跟随。

**存量（批 6 登录/注册/收藏/通用 i18n 化后，2026-09-27）**：基线 **83 行/16 文件 → 0 行/0 文件**（−83）——**i18n 主线收尾，存量清零**，
`scripts/i18n_hardcoded_baseline.txt` 只剩两行表头（此后任何新写死中文都是新文件违规，直接阻断）。
清零 16 个文件：`FavoritesView` 19、`RegisterView` 10、`RouteDebugPanel` 9、`BackupView` 6、`LoginView` 5、`LogBar` 5、`TableLoadFooter` 5、
`QueryHistory` 4、`StandardTable` 4、`SystemResources` 4、`useFavorite` 3、`UnifiedFilterBar` 3、`api/http` 2、`router` 2、`useQueryAdapters` 1、`LegacyRedirect` 1。
三语新增 12 个顶层命名空间（`favorites`/`register`/`route_debug`/`backup`/`logbar`/`table_load`/`query_history`/`standard_table`/`system_resources`/`http`/`legacy`/`query_adapters`）
+ 扩展 `login` 4 键 / `announce.type_long.*` 3 键 / `announce.detail.route_title`，叶子键 **772 → 860**（静态 75 + 动态/扩展 13）。
`router.ts` 两条详情路由的中文 `meta.title` 兜底删除、改用既有 `titleKey` 机制；模块级表 `typeTabs`/`STD_TYPE_LABEL`/`UnifiedFilterBar.types` 存 key、渲染期 `t()`；
非组件模块 `api/http.ts`/`useQueryAdapters.ts`/`useFavorite.ts` 走批 4 建好的 `i18n.global.t`。

---

### G-047：Python 侧 i18n 硬编码检查

**检查内容**：扫描 `pilotstd/`、`docker/` 下的 `.py`，统计 **AST 字符串字面量**（`ast.Constant` 且 `str`）
中命中中日韩统一表意文字（U+3400–U+4DBF、U+4E00–U+9FFF、U+F900–U+FAFF）的位置；
只有**超出基线**的部分才阻断。输出格式为 `文件:行号: 片段`。

**为何必须走 AST，不能用行级正则**（本门禁的判定核心）：
`check_g_012_comment_density.py` **强制要求注释与 docstring 必须是中文**。行级正则扫
`pilotstd/**/*.py` 会命中约 **8791 行**（其中注释 3417 + docstring 2152 正是 G-012 强制存在的中文），
而 AST 非 docstring 字面量口径只有约 **2055 处** —— **误报比约 4.6:1**，且会把门禁强制的规范判为违规
（**自我否证**）。故：
- **跳过 docstring**（`_docstring_lines()` 收集 `Module`/`FunctionDef`/`AsyncFunctionDef`/`ClassDef`
  的首个 `Expr(Constant[str])`，含三引号跨行的**全部行**）；
- **注释不在 AST 中**，天然不计。

**口径边界（明确声明）**：本门禁**含 `logger` 实参**（日志确实是给非中文用户看的内容，但 i18n 化收益低）。
按 P-104 采用**简单可辩护口径**（"Python 字符串字面量中的中文"），**不引入"日志豁免"**——
那需要判定调用者身份、增加误报来源。若要治理日志文案，应另立专项。

**存量基线**：`scripts/i18n_hardcoded_python_baseline.json`，格式 `{相对路径: 行数}`，机制与 G-040 一致：
- 文件不在基线里且有中文 → **全部算违规**（新文件必须一开始就走 i18n）；
- 文件在基线里但处数变多 → 只报多出来的（同一文件里新写死的中文照样拦得住）；
- 文件在基线里但处数变少 → 只打印 `[STALE]` 提示（不阻断）。

**空基线 ≠ 门禁失效**：上一条"文件不在基线里 → 全部违规"正是该护栏。G-040 曾因基线清零后
门禁看似失效而出过 CI 红（run `36293074107`），故 `tests/test_check_i18n_hardcoded_python.py`
专门有 `test_empty_baseline_still_blocks_new_file` 与 `test_missing_baseline_file_still_blocks` 两例锁定。

**扫描面与排除**：`SCAN_DIRS = ("pilotstd", "docker")`；排除任意层级的
`__pycache__`/`node_modules`/`build`/`dist`/`.venv`/`venv`/`tests`/`test`；
路径级豁免 `pilotstd/core/i18n.py`（语言包加载器本体，自身即本地化数据入口）。
**`scripts/` 不在扫描面**——门禁脚本面向中文维护者，i18n 化无收益。

**不继承 G-040 的一个缺口**：G-040 的 `collect_files()` 对**显式文件参数**跳过了 `is_scannable()`，
使 `check_i18n_hardcoded.py foo.py` 会真的扫 `.py`。本门禁**对显式目标也执行 `is_scannable`**，
保持"默认路径与显式路径判定一致"；对应受控用例 `test_explicit_target_also_filtered`。

**起因**（技术债阶段批次⑤）：G-040 只扫 `web/src/**/*.{vue,ts}`（其 `SCAN_SUFFIXES`），**Python 侧完全无门禁**
—— 今天往 `pilotstd/` 里写死中文，**13 道 CI 全绿**。设计文档 `notification-refactor-design.md` §6 排名 13 与
§7.3 已把它登记为"预存问题（本轮不修）"，并明确"若要治理，先加只拦新增的基线门禁，而非全量重写"。

**存量（首次接入，实测）**：**249 文件 / 2055 处**。首次运行即 PASS（扫描 399 个 `.py`，违规 0），
证明基线生成口径与判定口径一致。

**执行方式**：`python scripts/check_i18n_hardcoded_python.py`（`check_all.sh --fast` 与 CI `test-frontend` 步骤均已接入）；
辅助模式：`--report`（存量排行）、`--update-baseline`（偿还后收紧基线）、`<file|dir>`（只扫指定目标）。
受控测试：`tests/test_check_i18n_hardcoded_python.py`（**24 例**：基本判定 / **中文注释与 docstring 必须 PASS** /
跨行与模块级 docstring / **docstring 之后的普通字符串仍被报** / `i18n-allow` 行内与上一行 /
基线三态 / **空基线与基线缺失都必须拦** / 排除规则 / **显式参数也过滤** / report 不判失败 / 仓库基线完整自检）。

---

### G-048：架构文档模块计数一致性

**检查内容**：`docs/architecture/modules/core.md` 的「子模块数」行声明的数字，必须等于
`pilotstd/core/` 下**递归全部 `.py`** 的文件数。

**口径（显式写死，避免歧义）**：含 `__init__.py`、不含 `__pycache__`（其中为 `.pyc`）；
**统计文件系统而非 `git ls-files`**——后者看不见未纳入版本控制的文件，会放过"加了模块却忘提交/忘同步文档"的场景，判别力更弱。

**起因（实测）**：该行**自 2026-10-01 起连续漂移 12 个文件**（`8ccc8b85` 写 74 → 实测 86），
跨 2 天、涉及 5 个迁移实现 + 7 个通知模块，**长期无人察觉**——因为它不在任何门禁的比对范围内：
G-031 只校验"文档存在且映射齐全"，**不校验文档里的内容数字**。本门禁把"漂移"从"事后考古"变成"提交即红"。

**处置指引**：增删 `pilotstd/core/**` 下的 `.py` 后，在同一 commit 内同步该行数字（门禁输出会直接给出
声明值与实际值）。若计数合法变化（如新增模块），改文档即可；若不该变，则说明误加了文件。

**执行方式**：`python scripts/check_g_048_core_module_count.py`（已接入 `check_all.sh --fast`，
故 pre-commit 与 CI 的 `--fast` 路径均覆盖）。

**判别力（实测）**：临时在 `pilotstd/core/` 下新建一个 `.py` 而不改文档 → **EXIT=1**
（输出 `文档声明: 86 / 实际统计: 87`）；删除该文件后复跑 → **EXIT=0**。

---

### G-043：敏感端点审计接线

**检查内容**：用 **AST** 扫描 `docker/api/**/*.py` + `docker/auth.py` 的状态变更路由
（`POST`/`PUT`/`DELETE`/`PATCH`），对命中 `SENSITIVE_ROUTES` 的路由做 **L1 函数级**判定：
**该路由的函数必须可达 `write_audit`**；否则 FAIL。

**函数级判定的折中（AUDIT_WRAPPERS）**：可达性不靠"展开同模块全部辅助函数"——那会因
`trigger_cleanup → get_stats` 这类非审计调用而**假 PASS**。改为**显式注册表** `AUDIT_WRAPPERS`
（当前 8 条，含 `write_audit` 本体），配合 `validate_wrappers()` 自校验（每条必须真调用
`write_audit`）。**本方案以人工维护注册表换取判定精确性，不是消除依赖**。

**敏感端点判定标准**（三类，命中任一即纳入）：

| 编号 | 判据 | 本批示例 |
|------|------|---------|
| S1 | 凭证/密钥生命周期变更（创建、替换、轮换、撤销）与认证校验失败 | `PUT /api/notification/config`、`PUT /api/users/password`、`POST /api/settings/token/refresh`、`POST /api/login` |
| S2 | 权限与身份边界变更（改变谁能访问什么，或增删身份主体） | `POST /api/users`、`DELETE /api/users/{id}`、`POST /api/auth/register` |
| S3 | 不可逆批量数据销毁 | `DELETE /api/admin/logs`、`POST /api/cache/cleanup` |

**豁免**：`EXEMPT_ROUTES` 是**显式登记**的待接入清单，每条必须带理由字符串（禁止无理由豁免）。
**当前为空（0 条）**——L-01 批次把 6 项 P1/P2 端点（用户增删 / 自助注册 / 日志批删 / 缓存清理 /
手动备份）共 24 处出口全部接入；`POST /query` 本就函数可达 `write_audit`，移出豁免。
`[覆盖摘要]` 的豁免段现在**仅在 `exempted > 0` 时**输出。

**L2（出口覆盖）不进门禁**：门禁只做 L1。"产生状态变更的**出口**"无法纯静态判定（需理解语义），
故 L2 由**接线约定 + 测试断言**承担（见 `notification_coverage.md` 的 L-01 专项）。

**清单完备性提示（只提示不阻断）**：本门禁只校验两张清单**内**的路由，清单外路由不拦截。
`[覆盖摘要]` 给出**未登记的状态变更路由数量与前 10 项**（每项标注 `[已有审计]` / `[无审计]`），
实测当前 **55 项**。不阻断的理由：判定"哪个路由敏感"需**语义理解**（`POST /api/scan` 与
`PUT /api/notification/policy` 都改状态但敏感度不同）——与 L2 一致：无法静态判定者交给人。

**扫描范围**：`docker/api/**/*.py` + `docker/auth.py`（后者承接 `POST /api/login`、`POST /api/logout`
路由，不在 `docker/api/` 下；第 8 批纳入，否则登录路由对门禁不可见）。
注意 `docker/api/backup.py` **在扫描面内**，但其**读**端点 `GET /api/backup/list` 不在
`SENSITIVE_ROUTES`（只读不改状态，无留痕价值）；**写**端点 `POST /api/backup/create` 在清单内
且已接线（写 `BACKUP_CREATE` / `BACKUP_CREATE_FAILED`）。

**⚠️ `@require_role` 必须配 `request: Request` 参数（易踩陷阱）**：`require_role` 的实现是
**遍历 `args`/`kwargs` 查找 `Request` 对象**以读取 Cookie 中的 JWT。若端点签名无 `request`，
wrapper 取不到请求对象 → `current_role` 回落默认 `"user"` → **连 admin 也被 403**。
收尾 B 实测踩到：给 `GET /api/backup/list` 加 `@require_role("admin")` 后 admin 仍得 403，
直到补上 `request: Request`。护栏：`tests/test_backup_auth.py` 的
`test_admin_gated_endpoints_have_request_param`（静态检查多个文件的 admin 端点）。

**起因**（2026-09-26，第 2 批安全审计闭环）：全库仅 **4 处** `write_audit`
（`ACCESS_DENIED` / `DB_QUERY` / `SETTINGS_WRITE`），而使用 `@require_role` 的端点有 **61 处**；
改密、轮换静态令牌、改写通知渠道凭证这三类 P0 安全操作「放行不写审计」此前无任何门禁拦截。
同一轮还补齐了审计**读取**入口 `GET /api/admin/audit`（`docker/api/audit.py`）——此前
`read_audit` 无任何 API 暴露，审计只写不可读，等于死数据。

**执行方式**：`python scripts/check_sensitive_endpoint_audit.py`；
辅助模式 `--compare`（两套判定结论对比）、`--list`（列出敏感路由与接线状态）。
退出码 0=通过，1=存在未接线敏感端点。
**已接入**：`scripts/check_all.sh`（`--fast` 路径）与 `.github/workflows/ci.yml`。
受控测试：`tests/test_gate_unregistered_routes.py`（10 例，含 5 项注入验证）。

---

### G-044：术语与禁用词检查

**检查内容**：以 `docs/governance/glossary.json` 为唯一数据源（26 条术语），对 `pilotstd/i18n/{zh_CN,zh_TW,en}.json` 执行三条检测：

| # | 检测 | 阻断 | 说明 |
|---|------|------|------|
| 1 | **禁用词命中** | ✅ | `notification.*` 作用域内的值出现术语表 `forbidden` 词组（如 `保存完成`、`适配器`、`堆栈`、`未命中`） |
| 2 | **三语术语一致性** | ✅ | 术语表 `keys` 登记的键，三语值必须与登记值**严格相等**——防"改了简体忘改繁体" |
| 3 | `aliases` 命中 | ❌ 仅提示 | 值内出现可接受的同义写法（如 `消息`），打印 `::warning::` 但不阻断 |

**白名单三层**（均为显式登记，禁止无理由豁免）：① `exempt_keys`——该键整体跳过（配置字段名场景，如 `webhook_url`）；② `exempt_terms`——这些词在任何键内出现都不算禁用词（英文技术标识如 `bot_token`/`api_key`）；③ 行内 `_allow_legacy` 后缀——值以该标记结尾时跳过（与 G-040 基线策略同源）。

**作用域限 `notification.*`（209 键）**：界面标签（478 键）的用词自由度天然更高，且全量扫描会命中"保存项目/保存CSV"等**正确**用法。`forbidden` 只登记**词组**不登记单字，同理。

**起因**（2026-09-26，第 5 批术语治理）：实测语言包内同一概念多译法——`归档`(24 键)/`保存`(29 键)、`废止`(11)/`作废`(4)、`无法识别`(6)/`未识别`(5)、`未查询到`(6)/`未命中`(1)；且技术黑话残留：`适配器`(2 处，内部代号)、`堆栈`(1 处)；另有 `scan_complete` 与 `scan_empty` 标题**完全同值**（都是"扫描完成"）导致用户无法区分。同批修复 10 键文案并新增 `notification.scan.scan_complete.title.clean`（`failed==0` 时的标题变体，构建器按失败数分支选择）。

**执行方式**：`python scripts/check_terminology.py`；辅助模式 `--report`（空跑，仅报告不阻断，用于上线前验证）/ `--list`（列出术语表与白名单）。退出码 0=通过（可能带 aliases 提示），1=存在阻断项。
**已接入**：`scripts/check_all.sh`（紧跟 G-043，`--fast` 路径）与 `.github/workflows/ci.yml`（紧跟 G-043）。

---

### G-045：通知系统覆盖度基线

**检查内容**：以 `pilotstd/core/notification/events.py` 的 `ALL_EVENTS` 为事件全集，对每个事件校验三个**阻断**维度 + 一个**跟踪**维度：

| 维度 | 合格标准 | 性质 |
|------|---------|------|
| i18n | 该事件构建器调用的全部 `t()` 键在 zh_CN/zh_TW/en 三语中齐备 | 阻断 |
| e2e | 事件出现在 `tests/test_notification_e2e.py` 的 `EVENTS`，**且 `trigger_file` 物理存在** | 阻断 |
| 审计 | **安全类**事件（`security_*` / `notification_credential_changed`）的触发文件含 `write_audit(` | 阻断 |
| 术语登记 | 构建器键在 `glossary.json` 登记 | 跟踪（`--strict` 升阻断） |

**触发条件为什么包含 `trigger_file` 存在性**：只检查"事件在 EVENTS 列表里"不够——实测曾有 **3 处 `trigger_file` 指向已删除的 `_query_exec.py`**、**3 处安全事件记为投递管道 `security_notifier.py` 而非触发端点**（后者会让审计维度误判为"安全事件无审计"）。这类失真会让"有触发点"的断言变成**假绿**，正是无门禁时基线腐化的实证。

**基线文档**：`docs/governance/notification_coverage.md`（41 事件矩阵 + 新增事件 9 步准入清单；含 `<!-- BEGIN GENERATED MATRIX -->` 标记，**禁止手工编辑矩阵行**，改代码后重跑 `--matrix` 同步）。

**起因**（2026-09-26，第 11 批收尾审计）：通知治理完成 8 个功能批次后，缺少"全局覆盖度矩阵"证明所有事件在 i18n/测试/审计三维度无遗漏；且 5 处元数据失真长期潜伏——因为没有自动化校验。

**执行方式**：`python scripts/audit_notification_coverage.py`；辅助模式 `--matrix`（输出 Markdown 矩阵）/ `--strict`（术语跟踪项也阻断）。退出码 0=无阻断缺口，1=存在缺口。
**已接入**：`scripts/check_all.sh`（紧跟 G-044，`--fast` 路径）与 `.github/workflows/ci.yml`（紧跟 G-044）。

---

## 执行入口：`scripts/check_all.sh` 模式

| 模式 | 内容 | 是否写文件 | 归属 |
|------|------|-----------|------|
| `--fast` | G-010 代码规模、G-011 动态属性、G-015 相对导入、G-012 SQL Schema/注释密度、**G-048 架构文档模块计数**、**G-039 冲突标记**、**G-040 i18n 硬编码**、vue-tsc、G-027 组件 `defineOptions`、`_wait_worker` 防回潮 | 否 | 通用 |
| `--guards` | **治理守护（只读）**：Schema 一致性、G-032 文档健康度、G-037、G-030、G-033 | 否 | **入库产物**（CI 权威，本地 fail-fast） |
| `--local` | **本地专属**：G-031 文档联动同步 | 否 | **仅本地，禁止进 CI** |
| `--docs` | coverage.xml（缺失时生成）→ `generate_status_metrics.py` → `generate_coverage_report.py` → G-032 守护 | **是**（重写 `STATUS.md`、`docs/testing/coverage-report.md`） | 本地 |
| `--deep` | Ruff 全量、Mypy、G-020 Vulture、G-038、`--guards` | 否 | 入库产物（CI） |
| `--all` | `--fast` → `--docs` → `--deep` | 是 | 通用 |

### 检查的放置原则：**看它的输入在哪里可靠**

> 一个检查只能放在"它的输入确实存在且有意义"的那一侧。放错会得到**假绿**——
> 门禁跑着、也打印 PASS，但什么都没校验（本项目已发生过两次：docs 段被吞参、
> G-031 在直推 main 的 CI 里 diff 恒空）。

| 类别 | 判据 | 检查项 | 执行入口 |
|------|------|--------|---------|
| **本地专属** | 输入依赖本机状态或**待提交的变更集**，CI 里不存在/恒空 | **G-031**（`origin/base..HEAD` 在直推 main 的 CI 中恒为空 → 假绿） | 仅 `--local`（pre-commit 钩子） |
| **含本地产物的混合型** | 同一脚本同时覆盖本地文件与入库文档，缺失侧降级 | **G-032**（`STATUS.md` 为 gitignored 本地文件；`coverage-report.md` 入库） | 本地经 `--guards` 完整校验；CI 直接调用脚本，入库文档维度生效、`STATUS.md` 维度自动放行 |
| **入库产物** | 校验对象是提交进仓库的代码/文档 | Schema 一致性、G-037、G-030、G-033、G-038（`--deep`）、check_docs_sync.py、`check_capabilities_sync.py` | **CI 为权威**（`trinity-gate.yml` 的 `--deep`；`ci.yml` repo-compliance 的显式步骤）；本地可跑一份做 fail-fast |

| 环节 | 在哪执行 | 说明 |
|------|---------|------|
| **文档生成** | **仅本地**：`bash scripts/check_all.sh --docs` | 产物 `STATUS.md` 为 gitignored 本地文件；`docs/testing/coverage-report.md`、`docs/governance/capabilities_registry.md` 入库，人工确认后提交 |
| **本地专属检查** | pre-commit 钩子：`--fast --guards --local` | G-031 在提交前提示"改了代码要同步改文档"（已并入暂存区变更，否则提交前看不到本次改动） |

- **多模式可叠加**：`check_all.sh --fast --guards --local` 依次执行三个模式（2026-09-13 修复：
  原实现 `MODE="${1:---fast}"` 只取第一个参数，导致 pre-commit 钩子里写的
  `--fast --docs` 实际只跑 `--fast`，docs 类门禁形同虚设；未知参数现在直接报用法并退出 1）。
- **pre-commit 钩子**（`.husky/pre-commit`）执行 `--fast --guards --local`：不用 `--docs`
  （生成属本地行为，且会重写工作树并重跑带覆盖率采集的 pytest）。
- **CI 不生成文档**：`trinity-gate.yml` 执行 `--deep`（不含 `--docs`、不含 `--local`），
  已移除原先空转的 pytest 采集与 artifact 上传步骤。
- **G-038 仍在 `--deep`**：它需要 PATH 上存在 `ruff`/`mypy` 可执行文件，各开发机是否安装不一致，
  故不纳入提交时门禁；CI 的 test-backend job 用 venv 内的 ruff 强制执行。
- **G-031 ≠ CI 的 check_docs_sync.py**：前者 12 条映射（多覆盖 `scripts/`、`.github/workflows/`、
  `docs/governance/`、`docs/architecture/decisions/`），**只放本地**；后者 5 条模块映射，
  校验**入库**文档，留在 CI。两者规则集不同、互补，不做替换。
- **能力矩阵同步在 CI**：`docs/governance/capabilities_registry.md` 是入库文档，
  由 `scripts/check_capabilities_sync.py`（重生成 → 剔除生成时间戳行比对 → 还原文件）
  在 `ci.yml` repo-compliance 校验；生成动作仍在本地，由 AGENTS.md 第七节要求人工重跑并一并提交。

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.77 | 2026-10-03 | **工具调用收口（终）：G-020 的 vulture 同样改用 `python -m vulture`（独立 commit）**。**背景**：v1.75/v1.76 已修好 ruff/mypy/G-038 的 PATH 调用，但 `check_all.sh` 的 G-020 仍以裸 `vulture` 调用（本机 `python -m vulture --version`＝2.16 可用，可执行文件不在 PATH）→ 报 `vulture: command not found` → **G-020 误报 FAIL、`--deep` 整体红灯**。**改动**（仅调用方式）：`if vulture …` → `if python -m vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100`，扫描范围、阈值与 `whitelist.py` 参数**均不变**；并在该段补成因注释（防回退）。**至此 `check_all.sh` 内再无裸工具调用**（ruff／mypy／vulture 三处全部 `python -m`）。**受控实验（判别力）**：修复后 vulture **真的执行**并检出 **2 处真实问题**（`tests/test_notification_stage2b_enable_grey.py:165` 与 `:523`：`unused variable 'tz' (100% confidence)`，退出码 3）→ `--deep` 的 G-020 以**真实检出** FAIL（**不再是"命令不存在"**），证明该门禁**会因真实问题阻断**。同批 `✅ Ruff 全量检查`、`✅ Mypy 类型检查`、`✅ G-038 历史遗留错误清零`。**遗留（未修，另立）**：上述 `tz` 是**为匹配被覆写的 `datetime.now` 签名而故意保留**的参数（作者已用 ruff 行内抑制，而 vulture 不读该注释）——属"抑制机制缺口"而非代码缺陷；修复须走项目既有的 `whitelist.py` 机制或改名，**需另行裁决**（本轮只改调用方式）。 |
| v1.76 | 2026-10-03 | **新增 G-048（架构文档模块计数一致性）＋ `core.md` 计数修正（74/75 → 86）**。**背景（实测口径溯源）**：`core.md` 的「子模块数」自 `8ccc8b85`（2026-10-01）写下 **74** 后**连续漂移**——在同一口径（`pilotstd/core/` 递归全部 `.py`，含 `__init__.py`）下，该提交实测恰为 **74**（口径一致、非口径歧义），此后 2 天内新增 12 个文件（5 个迁移实现 + 7 个通知模块，含步 A C1 的 `channel_spec.py`）至 **86**，全程无门禁察觉（G-031 只校验"文档存在 + 映射齐全"，不校验内容数字）。**改动**：① `docs/architecture/modules/core.md` 的「子模块数」改为 **86**，并**显式写明口径 + 截至日期 + 顶层构成**（3 个包 config/db/notification + 22 个直属模块），删除与实际不符的旧括注「安全 / 工具」；② 新增门禁脚本 `scripts/check_g_048_core_module_count.py` 并接入 `check_all.sh --fast`（pre-commit 与 CI 的 `--fast` 路径同时覆盖），**统计文件系统而非 `git ls-files`**（后者看不见未纳入版本控制的文件，判别力更弱）；③ 本文件补 G-048 表行、详述节与 `--fast` 模式行。**判别力（受控实验）**：临时新建一个包内 `.py` 而不改文档 → **EXIT=1**（`文档声明: 86 / 实际统计: 87`）；删除后复跑 → **EXIT=0**；探针已清理（`git status` 无残留）。**同批修正（自检发现）**：v1.75 行文中把探针写作一个**不存在的文件名**，被 G-032 交叉引用检查判为"引用了不存在的文件"（警告 16 → 17）——已改写为"影子模块"描述，不再产生该噪声。 |
| v1.75 | 2026-10-03 | **工具调用收口（续）：G-038 的 ruff/mypy 同样改用 `sys.executable -m` 调用（独立 commit）**。**背景**：v1.74 只修了 `check_all.sh` 的 L1/`--deep` 两处调用；`scripts/check_g_038_legacy_errors.py:31,49` 仍以裸 `["ruff", …]`／`["mypy", …]` 调 `subprocess`，`:40,:59` 捕获 `FileNotFoundError` 后返回**失败**（非跳过）→ 本机 `--deep` 的 G-038 以「ruff 未安装，请执行: pip install ruff」**误报红灯**（与 `--fast` 的 L1 已修好的状态不一致，deep/fast 口径分裂）。**改动**（仅调用方式）：两处命令列表改为 `[sys.executable, "-m", "ruff"|"mypy", …]`，扫描范围/参数/超时/裸 noqa 检查**均不变**；并在常量区补成因注释（防回退）。**语义不变**：模块真缺失时 `python -m` 以非零码退出 → `returncode == 0` 为假 → `main()` 仍 `return 1` **阻断**（不是跳过）。**受控实验**：① 正常运行 `python scripts/check_g_038_legacy_errors.py` → `✅ G-038 通过` EXIT=0；② 判别力——用 `PYTHONPATH` 加载一个**抛导入错误的影子模块**（模拟"模块不可用"，探针在仓库外临时目录创建）→ **EXIT=1** 且打印 `Ruff 检查失败` + traceback（**证明确实阻断而非跳过**）；③ 复原 → EXIT=0。**`--deep` 实测**：`✅ Ruff 全量检查`、`✅ Mypy 类型检查`、`✅ G-038 历史遗留错误清零` 三项均 PASS（`--deep` 整体仍 EXIT=1，原因见下条）。**同批次发现（未修，另立）**：`scripts/check_all.sh:334` 仍以裸 `vulture` 调用（本机 `python -m vulture --version`＝2.16 可用但不在 PATH）→ `--deep` 的 G-020 报 `vulture: command not found` 而 FAIL，**同类 PATH 缺陷的第 3 处**，建议按同一方式收口。 |
| v1.74 | 2026-10-03 | **工具调用收口：L1/L2 快速 lint 的调用方式由 PATH 可执行文件改为 `python -m`（修复"已安装却被判未安装"的静默漏检）**。**现象**：`run_lint_fast` 以 `command -v ruff`／`command -v mypy` 探测，而本机两工具**确已安装**（`python -m ruff --version`＝0.15.17、`python -m mypy --version`＝2.1.0），只是**可执行文件不在 PATH** → 判定「未安装」并降级 WARN 跳过，**所有改 `.py` 的提交都漏检 lint**（2026-10-03 步 A C1 批次靠人工补跑才发现并修掉 1 个真实 `F401`）。**改动**（仅调用方式；扫描范围、参数、判定分支与"模块真不可导入时仍只 WARN 不阻断"的既有语义均不变）：`scripts/check_all.sh` 的 4 处调用点 `ruff check …` → `python -m ruff check …`、`mypy …` → `python -m mypy …`，探测改 `python -m ruff --version` / `python -m mypy --version`；`run_deep()` 的同两处同步改（否则 `--deep` 与 `--fast` 的 lint 口径会分裂）。**受控实验**：`bash scripts/check_all.sh --fast --with-lint` 由「⚠️ 未安装 → 跳过」变为 `✅ L1 ruff check`（`All checks passed!`）＋ `✅ L1 mypy`（`no issues found in 404 source files`）；提交钩子同验（commit `02aa9288` 的 pre-commit 已实际执行上述两项）。**同批次发现（未修，另立）**：`scripts/check_g_038_legacy_errors.py:31,49` 以裸 `ruff`／`mypy` 调 `subprocess`，`:40,:59` 捕获 `FileNotFoundError` 后返回**失败**（非跳过），故本机 `--deep` 的 G-038 会以「ruff 未安装」**误报红灯**——同类 PATH 缺陷，建议按同一方式收口。 |
| v1.73 | 2026-10-01 | **R16：清空候选池 P0~P3（门禁受控测试自动化 + schema 门禁提示 + T-30 收口）**。**P0**：`scripts/check_all.sh` 新增 `run_gate_selftests` —— `--fast` 下暂存变更命中 G-040 基线或其门禁脚本（含**删除**，`--diff-filter=ACMRD`）即自动跑 `tests/test_check_i18n_hardcoded.py`；`--deep` **无条件**跑一遍（CI 的 `trinity-gate.yml` 会执行 `--deep`，故 CI 侧同样兜住）。**受控实验**：删基线文件并暂存 → `--fast` FAIL(1 failed/19 passed)、`--deep` FAIL；无门禁变更则跳过（`--deep` 除外）。**P2**：`scripts/check_schema_consistency.py` 的 MISSING 分支补两行指引（中性表名 + `ALTER TABLE … RENAME TO`）。**P3**：T-30 按「队列效应消除」收口（指标重定义为「首个作业启动 ≤20s 且旧组同窗 ≥100s」）并归档。**P1**：scripts/check_docs_sync.py → `scripts/check_module_doc_mappings.py`（`git mv`；两脚本头部互指职责边界），同步 `ci.yml`／受控测试／本文件历史行的反引号引用（去反引号以保 G-032 13 不增）；**T-16 计数按既定口径归零重算**（仪器已换）。观察项活跃 **12 → 10**（T-30 + T-25 残留先后归档），全部保留项仍带状态标签。 |
| v1.72 | 2026-10-01 | **R14-5：适配器模板状态字典同步 + 技术债台账归档整理与存续项校准**。**任务一**：`pilotstd/templates/adapter/**` 状态字面量改引 `Status.*.value`（归一方向不变）；新增生成物契约测试 `tests/unit/test_adapter_template_generation.py`（10 例，覆盖四种 `response_type` 分支的渲染 + `ast.parse`/`py_compile` + 零裸字面量扫描 + import 行 `exec` 验证），并当场修复模板 **3 类缺陷**（3 处伪占位符／48 处 `-%}` 吞缩进／1 处死条件片段——默认配置此前会生成**不可编译**的适配器）。**任务二**：台账版本 v1.43.0 → **v1.44.0**；「一、已清理」改为历史归档区并补 4 条归档；「二、剩余台账」明写**存续 0 条**；「三/四/五」加状态标注；「六、观察项」**16 条逐条加状态标签 + 新增状态汇总表**，并**补登 4 条 R14 复盘的隐性债务**（SQL 内嵌状态字面量／cookiecutter CLI 未入依赖／本地网络用例挂起／schema 一致性门禁约束无提示）；内部链接死链 **0**。 |
| v1.71 | 2026-10-01 | **R14-4d：#32-D 测试侧收敛 + 哨兵机制（#32 正式闭环）**。`tests/` 中文状态字面量 **513 → 25 处**（替换 456 处／67 文件，AST 口径排除 docstring）；刻意保留 **5 处哨兵**（`tests/unit/core/test_status.py` 字典 9 值／`tests/unit/core/test_status_convergence.py` 扫描基准／`tests/unit/core/test_status_contract.py` API 历史中文入参／`tests/test_format_utils.py` 解析层外部输入／`tests/unit/core/test_migrate_v61.py` DB 历史 DDL），均带 `# Sentinel: 确保枚举 value 与现网中文契约一致` 注释与断言。**纯测试侧改动**：生产代码／DB 迁移／前端零改动，未删除任何用例。**验证**：全量测试 **4356 passed / 6 skipped**；ruff/mypy 全绿；`--fast --guards --local` 与 `--deep` EXIT=0；CI 13/13。**#32 由「二、剩余台账」移入「一、已清理」（A→D 四阶段闭环）。** |
| v1.70 | 2026-10-01 | **R14-4c：#32-C 贯通 API 契约 + 落库迁移 + 前端 i18n 映射**。**API**：`pilotstd/core/status.py` 新增 `status_key()`／`resolve_status_filter()`；`/api/standards/status`、`/api/query/results`、`/api/pending/requery` 新增 `status_key`（中文 `status` 保留，**向后兼容**）；`/api/wechat-ip/status` 新增 `current_ip_known`。**DB**：新增 v61 迁移（`_migrate_v61_enum_status_defaults.py`）把 `file_index.status`／`standard_validity.status` 列默认值收敛到字典——无漂移**不重建**（零数据搬动）、漂移时 12 步重建修复；**未改历史迁移源码（P-106）**；`CURRENT_SCHEMA_VERSION` 60 → 61。**前端**：新增 `web/src/utils/stdStatus.ts` 为状态比较唯一事实源，13 处中文状态比较 → **0**（`i18n-allow` 状态项清零）；筛选下拉提交英文键（后端双口径兼容）。**测试**：契约 25 例／迁移 6 例／前端 4 例；核心+迁移回归 506 passed；前端 vitest 301 passed；`vue-tsc -p tsconfig.app.json` 零错误；i18n 三语对齐 PASS；schema 一致性 PASS。**验证**：`--fast --guards --local` 与 `--deep` 均 EXIT=0；CI 13/13。 |
| v1.69 | 2026-10-01 | **R14-4b：#32-B 后端业务字面量大收敛（199 处，5 个原子 commit）**。按域分批：B1 `pilotstd/core`+`announcement`+`pipeline`(27) → B2 `pilotstd/query`(96) → B3 `pilotstd/manager`(32) → B4 `pilotstd/ui`(39) → B5 `docker`(5)；统一改为 `Status.<MEMBER>.value`（API/DB/日志/SQL 参数处严格 str，**API 契约零变化**）。**计数（tokenize）**：生产 **220 → 21 处**＝9 处枚举定义（`pilotstd/core/status.py`，字典本身）+ 12 处 cookiecutter 适配器模板（`pilotstd/templates/adapter/**`，含 Jinja 占位符、非运行时代码）→ **运行时业务代码 199 → 0** ✓。**新增守卫** `tests/unit/core/test_status_convergence.py`（AST 扫描生产目录断言零裸字面量／`ValidityChecker` 行为断言／枚举 round-trip）。**文档联动**：core.md／announcement-pipeline.md／query.md／manager.md／ui.md 补字典引用说明（按批次同 commit，G-031）。**验证**：分批回归 393/284/381/1829 passed；ruff+mypy 每批全绿；`--fast --guards --local` 与 `--deep` EXIT=0；CI 13/13。 |
| v1.68 | 2026-10-01 | **R14-4a：#31 正式闭环（P3 降级观察）＋ #32-A 状态字典落地（零行为变化）**。**#31**：用户裁定 P3（跨进程文件锁）**降级为观察项 T-35**——P2+P1 后单批查询写盘 126→2、构造 133→1，跨进程同毫秒写冲突概率可忽略，文件锁跨平台语义/边缘情况维护成本高于防范收益；**#31 由「二、剩余台账」移入「一、已清理」**（核心闭环），台账「二」现只列 #32。**#32-A**：新增 `pilotstd/core/status.py`（`Status` 枚举 9 值，value 与现网中文**逐字一致**；`STATUS_I18N_KEYS`/`STATUS_EN_KEYS` 映射脚手架；`normalize_status()` 归一 `废止`→`已废止`；5 组命名集合），并把 **9 处容器定义**（`pilotstd/manager/classifier.py`、`pilotstd/manager/facade/_organize.py`／`pilotstd/manager/facade/_query.py`／`pilotstd/manager/facade/_query_subsystem.py`、`pilotstd/organizer/mover.py`、`pilotstd/core/notification/_format_utils.py`、`pilotstd/ui/core/handlers/auto_flow_engine.py`／`pilotstd/ui/core/handlers/query_flow_engine.py`、`docker/api/standards.py`）改为引用该字典，**取值逐一等价**；**未替换业务字面量、未改迁移脚本、未改 API 返回**。**字面量计数（tokenize）**：生产 **248 → 220 处**（−37 容器字面量 +9 枚举值；其余业务 198 处未动，9 个容器文件内另 13 处业务字面量未动）；测试 456 → 504（新增用例基准；D 阶段收敛）。**新增用例** `tests/unit/core/test_status.py` **16 例**（其中 UI 侧容器断言用 `pytest.importorskip("PyQt6")` 环境守卫——后端作业不装 GUI 依赖，无 PyQt6 时为 15 passed + 1 skipped；CI 首跑红灯 `ModuleNotFoundError: PyQt6` 即由此修正）；受影响模块回归 768 passed（4 例 aggregator 失败经 HEAD worktree 对照证实为既有顺序干扰）；**架构文档** `docs/architecture/modules/core.md` 补状态字典设计意图（G-031 强制同步）。**验证**：`--fast --guards --local` 与 `--deep` 均 EXIT=0；CI 13/13。 |
| v1.67 | 2026-10-01 | **R14-3b：#31-P1 落地——共享 ConfigManager 实例 + 显式配置失效通知**。**改动**：`pilotstd/core/config/manager.py` 新增 `get_shared_config()`／`invalidate_shared_config()`／`register|unregister_invalidation_listener()` 与 `save()` 写盘后的失效发布（`_SHARED_LOCK`＝**可重入锁**，首次运行写盘会重入）；消费方 `query/routing/scorer.py::get_profile`、`query/site_config/_loader.py::_load_site_overrides`、`pilotstd/core/config/service.py` 改从共享实例取；站点配置模块注册清缓存监听者。**受控矩阵**：`test_parallel_batch_query` `__init__` **133 → 7**（热路径 **1**＝共享实例冷启动；另 **6** 为一次性 DB 迁移读配置、落在 `@migration` 函数体内受 **P-106** 保护）、**稳态 50 次 `get_profile` 构造 1 → 0**、`save()` **保持 2**（P2 未破坏）、`get_profile` 耗时 **577 → 5 ms**（单次 0.04 ms）。**新增用例 12 例**（共享/失效 8 ＋ 热路径端到端 4，含“无 TTL”与“GUI 写盘后热路径读到新值”）；回归 **826 passed / 1 skipped**；**架构文档** `docs/architecture/modules/core.md` 补失效通知数据流（G-031 强制同步）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；CI 13/13。**未触** P3（跨进程锁）与 P2 dirty 语义，未改任何函数签名。 |
| v1.66 | 2026-10-01 | **R14-3a：#31-P2 落地——`_load()` dirty 写盘（消除热路径整份覆盖写）**。**改动**：`pilotstd/core/config/manager.py::_load()`“文件已存在”分支改为**快照内存态 → 补默认值 + 迁移旧键 → 仅内容变更才 `save()`**（原无条件写回）＋新增 `import copy`；**未触 P1（缓存/注入）与 P3（跨进程锁）**。**四条契约保持**：①首次创建写盘 ②补默认值/迁移有变更写盘一次 ③`set()`+`save()` 持久化 ④损坏文件先备份 `.corrupted.<ts>` 再写。**受控矩阵（同探针前后）**：`test_parallel_batch_query` `save()` **135 → 2**（−98.5%）、`get_profile` **577 → 153 ms**（单次 4.58 → 1.21 ms）、`__init__` 133 不变；对照用例 26 → 1；单批无谓覆盖写 **≈519 KiB → ≈7.7 KiB**。**新增用例** `tests/unit/core/config/test_manager_dirty.py`（7 例：首建写盘／完整零写盘／补默认值写一次／旧键迁移写一次＋幂等／`set()` 不写盘而 `save()` 落盘／损坏备份／`reload` 零写盘）。**回归**：20 个引用 ConfigManager 的文件集 **697 passed / 1 skipped**；Ruff/Mypy/G-020/G-038 全 PASS。**文档联动**：`docs/architecture/modules/core.md`「配置」条目补写盘语义与量化收益（G-031 强制同步）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；CI 13/13。 |
| v1.65 | 2026-10-01 | **R14-2（阶段一）：#31／#32 原挂窗项盘点与攻坚方案（只出调查与方案，不动业务代码）**。**盘点**：两项窗口（原定第十二轮、锚 `v0.119.x→v0.120.0`）**均已逾期**（当前 `v0.120.2-2-gcf70b6ad`）；按用户裁定**推翻 #32 行的“自动转已接受”条款**并**窗口重锚**（#31→R14-3、#32→R14-4，仅此一次）。**今日只读复测**：#31 `test_parallel_batch_query` 实测 `ConfigManager.__init__=133`／`save()=135`／`get_profile=126`（577 ms，4.58 ms/次；对照 25／26／21）→ 单批 ≈0.58 s＋≈519 KiB 写盘；生产构造点 21 处、引用测试 31 文件、`save` 相关测试断言 57 行／`_get_fernet` patch 39 行／`save.*assert` 33 处。#32 生产字面量 **248 处／50 文件**、测试 **456 处／65 文件**、容器 **9 处／5 名**、前端 `i18n-allow` 27 行（状态值比较 13 处）、DB 默认值 3 处（与 R11-2 逐项一致）。**拆分**：#31 → R14-3a（P2 dirty 标记，1 周期）／R14-3b（P1 实例复用+失效通知）／R14-3c（P3 跨进程锁，可转观察）；#32 → R14-4a（A 枚举落地，零行为变化）／R14-4b（B 后端收敛）／R14-4c（C 契约+迁移+前端）／R14-4d（D 测试收敛）；**合计 8~13 周期**。**裁定**：先 #31（活的数据丢失+性能缺陷），#32 紧随；两者无前置依赖，可按需对调。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.64 | 2026-10-01 | **R14-1：T-27 修复——入仓合规检查「新增文件」在推送路径上恒空（假绿）闭环**。**根因**：`.github/scripts/check-repo-compliance.sh` 用 `git diff --diff-filter=A "origin/<base>..HEAD"` 取“本次新增文件”，而**推送事件**触发时 CI 已把 `origin/<base>` 推进到本次 tip（`origin/main == HEAD`）→ 范围恒空 → 恒 `PASS: 无新增文件`，白名单/黑名单/根目录可疑文件判定**从未在推送路径生效**（CI 日志实证 run 36304263963 / 36306033918）。**修复**（与 docs-sync 的 T-25/R11-3b 同一手法）：① `.github/workflows/ci.yml` 的 `Run repo compliance check` 步骤新增 `COMPLIANCE_RANGE: ${{ github.event.before }}..${{ github.sha }}`；② 脚本优先使用该范围，`before` 为空/全零时回退 `origin/<base>...HEAD`（三点＝merge-base）；③ **假绿防护**：显式范围“变更文件数 == 0” → FAIL（拒绝静默 PASS）；④ `--diff-filter=A` → **`AR`**（改名后的目标路径同样受检，堵住改名绕过）；⑤ 新增诊断行 `范围: …（变更 N 个文件，其中新增/改名 M 个）`。**受控矩阵（临时 bare 远端忠实复刻推送态）6/6 通过**：假绿复现 → 修复后拦截、白名单不误拦、仅修改不误触防护、显式 0 变更 FAIL、`before` 全零回退不硬失败、改名命中黑名单 FAIL。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；CI 13/13。 |
| v1.63 | 2026-10-01 | **R13-2：T-33 + T-34 合并收口（`tests/` 永久 skip 归零 + 本地 G-020 口径对齐 CI）**。**① T-33**：删除 `tests/gui/` 下的 `test_e2e_settings` 与 `test_e2e_settings_io` 两个空壳文件（二者均为 `def test_x(): pass` **空壳 skip 占位**，自述已由 `test_settings_announce.py`／`test_settings_dialog.py` 覆盖）→ 静态普查 **`mark_skip` 2 → 0**；`tests/test_skip_census.py` 受控基线 `== 2` → **`== 0`**（新增永久 skip 必须登记并同步主簿）；同步引用文档：`docs/testing/e2e-test-manifest.md`（两行 → R13-2 说明）、`docs/guides/settings-io-engine-pattern.md:178`（改写为“空壳已删除”）、《技术债主簿》「四、已跳过测试」T-10 两行 + 更正注记。**② T-34**：`scripts/check_all.sh` 的 G-020 命令由 `vulture pilotstd/ --min-confidence 80` 对齐为 **CI 完全一致**的 `vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100`（并加注释说明 R13-1 的成因：本地口径窄 → `tests/` 内 100% 置信度死代码本地不可见）。**依据**：本地绿灯必须等价于 CI 绿灯，否则 `--deep` 失去“提交前最后防线”意义；代价＝本地 vulture 增加 3 个目录，耗时 +<2s。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0（含对齐后的 vulture）；`mark_skip == 0`。 |
| v1.62 | 2026-10-01 | **R13-1b：CI 首跑红灯修正 + 新观察项 T-34（本地 G-020 口径窄于 CI）**。**失败**：run `36795410642`（sha `0d501ee6`）`test-backend` failure → 下游 `test-gui-coverage`／`version`／`docker`／`exe` 连带 skipped。**根因**：`tests/unit/manager/facade/test_query_subsystem_snapshot.py:186` 的 `def _engine(tuples, …)` 未用参数被 CI 的 `vulture … tests/ … --min-confidence=100` 判为 100% 置信度死代码；**本地 `--deep` 的 G-020 只扫 `pilotstd/`、阈值 80** → 口径差导致“本地绿、CI 红”。**修正**：参数改名 **`_tuples`**，本地按 CI 原命令复跑 **EXIT=0**，受影响三文件 **40 passed**。**新观察项 T-34**：建议一行对齐本地 vulture 口径与 CI 一致（待用户放行；P-103／P-107 不越界改门禁）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.61 | 2026-09-27 | **R13-1：T-29 清零——`tests/` 8 处永久 `@pytest.mark.skip` 全部转为真实用例**。**改动**：`tests/unit/manager/facade/test_query_subsystem_snapshot.py`（4 处 → 5 个真实用例：公告缓存四分支／缓存优先+引擎降级回填／`_finalize_query` 统计与通知（含空结果 `query_empty`+`record_pending`）／`query()` 缓存分支+进度接线）与 `tests/unit/query/engine/test_batch_dispatch.py`（4 处 → 4 个真实用例：`_init_batch_state` 心跳与计数／`_bucket_worker` 双路径／`_dispatch_queries` 并行编排+溢出汇总／`_finalize_batch` 组装与状态复位）；全部用 mock/monkeypatch 驱动真实逻辑（不触网、不起真实组件）；**0 xfail、0 删除**。**关键发现**：原 8 处**函数体均为 `pass` 空壳**（skip 掩盖的是“从未写过的测试”）。**测试侧同步**：`tests/test_skip_census.py` 基线 `mark_skip >= 8` → **`== 2`**，并新增“T-29 两文件零永久 skip 且无 `pass` 空壳”断言（新观察项 **T-33** 登记余下 2 处 GUI 空壳）。**证据**：两文件 **26 passed+8 skipped → 34 passed（0 skipped）**；静态普查 `mark_skip` **10 → 2**；后端全量 **4033 passed/14 skipped → 4040 passed/6 skipped**（+7／−8 自洽）；GUI 全量 **1022 passed** 不变；`test_skip_census.py` 6 passed。**后端 6 处 failed 与本次改动无关**：已在 `HEAD` 独立 worktree 复跑对照（修复前同样失败 4 处 test_manager，均为本地网络/worker 环境所致，CI 以 iptables 屏蔽外网）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.60 | 2026-09-27 | **R12-8②：#34 ✅ 已修复——内部锁换 `threading.Lock`，三重回归门全绿**。**门①探针有效性**：`scripts/probe_mutexlocker_race.py --lock qt` **37/100 崩（37.0%）**；**门②对照**：`--lock python` **0/100 崩**；**门③CI 端到端**：`gui-race-probe` run `36725863997`（sha `b3dc567a`）**`2026-09-30T15:29:39.1821302Z === RESULT: loops=50 failures=0 ===`**（结论 `success`）；**附加本地端到端**：`scripts/probe_race_minimal.py` 修复后 **0/100 崩**（修复前 47/100）。**测试**：`tests/gui/test_event_bus_integration.py` 19 passed。**#34 由「二、剩余台账」移入「一、已清理」**，候选池 **P6 关闭**，T-26 观察项关闭；保留两个诊断脚本与 `gui-race-probe.yml` 作回归工具，R1 测试侧兜底保留（纵深防御）；**新哨兵**＝任何 GUI 作业再现 access violation 即重跑探针（loops=50）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.59 | 2026-09-27 | **R12-8①：EventBus 内部锁 `QMutex`+`QMutexLocker` → `threading.Lock`（#34 根因消除）**。**改动**（仅锁相关代码，未动业务逻辑/订阅者管理/世代号/reset 协议）：`pilotstd/ui/core/event_bus.py` —— 类级 `_lock = QMutex()` → **`threading.Lock()`**；3 处 `with QMutexLocker(cls._lock):` → `with cls._lock:`、4 处 `with QMutexLocker(self._lock):` → `with self._lock:`；移除 `QMutex`/`QMutexLocker` 导入、新增 `import threading`；模块文档与注释同步说明 R12-8 根因（其余说明保留）。**未引入任何第三方依赖**，**未保留 QMutex 备选路径**。**依据**：R12-7 二分（变体 C：Qt 锁 + 线程 churn 6/14 崩；变体 D：仅换 `threading.Lock` 0/14 崩，p≈0.007）+ WER 转储原生证据（`PyWeakref_NewRef+0x114`，READ @ 0x8）。**本地验证**：`tests/gui/test_event_bus_integration.py` → **19 passed / 103.6s**；Ruff/Mypy 通过。**三重回归门**：本地 ① `probe_mutexlocker_race.py --lock qt`（探针有效性）、② `--lock python`、③ 修复后端到端 100 轮——结果与 CI `gui-race-probe -f loops=50` 结果记入 R12-8②（主簿 7.22）。 |
| v1.58 | 2026-09-27 | **R12-7：最小化复现 + 根因二分定位（#34）**。**新增两个诊断脚本**（均不参与 pytest 收集）：`scripts/probe_race_minimal.py`（复刻并发订阅 + reset 流程，脱离 pytest）与 `scripts/probe_mutexlocker_race.py`（**纯 PyQt6**，不含本项目代码，`--lock qt|python` 切换锁实现）。**阶段一**：`probe_race_minimal.py` 单轮 **0.92~1.4s**、**100 次运行 47 崩（47.0%）**，全部 `0xC0000005`，落点 `event_bus.py:127`/`:86` 的 `with QMutexLocker(...)`。**阶段二**：PageHeap（`gflags`/`appverif`）需写 HKLM IFEO，本会话**无管理员权限**（实测拒绝）、WinDbg MSIX 无 `cdb.exe` → 改用 **HKCU WER LocalDumps + minidump/pefile 离线解析**：`ExceptionAddress=python312.dll+0x54484 → PyWeakref_NewRef+0x114`、**READ @ 0x8**。**决定性二分**（`probe_mutexlocker_race.py`）：长寿命线程 0/12 崩 → **线程 churn + `QMutexLocker` 6/14 崩** → **仅换 `threading.Lock` 0/14 崩**（p≈0.007）⇒ **根因＝PyQt6 Qt 锁 × 线程反复创建/销毁的 sip 弱引用记账竞态，与 EventBus 业务逻辑无关**。**R12-8 候选（未实施）**：`EventBus` 内部锁改 `threading.Lock`，并以上述两探针作回归门。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.57 | 2026-09-27 | **R12-6：本地 CI 同口径复现（Python 3.12.10 + PyQt6/Qt 6.11.2）**。**做法**：per-user 安装官方 Python **3.12.10** + 隔离 venv（仓库外 `C:\Temp\pilotstd-probe\venv312`），按 CI 真实口径装 `PyQt6==6.11.0` + **`PyQt6-Qt6==6.11.2`**（`qVersion()` 校验）+ sip 13.12.0 + pytest 9.1.1，仓库零改动；按 `gui-race-probe` 等效方式跑 `tests/gui/test_event_bus_integration.py` **50 轮**（逐轮独立进程 + `PYTHONFAULTHANDLER=1` + 逐轮日志）。**结果**：**failures=3**（单轮 min=48.5s / max=114.7s / 均=100.5s）——✅ 本地复现成功，崩溃现场已存档，按用户裁定不自行修复，等 R12-7 裁定。 **验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.56 | 2026-09-27 | **R12-5 结果：环境 pin 校正（Qt 运行库 6.11.2 确认）+ `reset()` 保活单例 + 回归门**。**① pin 校正**：`gui-race-probe.yml` 改 `shell: pwsh` + 严格错误处理（原先 `pip install PyQt6==6.11.2`（PyPI 无此版本）静默失败）、改钉 **`PyQt6-Qt6==6.11.2`** 并断言 **`qVersion() == 6.11.2`**；快检 run `36428298369` 指纹通过。**口径纠正**：`QT_VERSION_STR` 是 PyQt6 编译期常量，运行库版本须看 `qVersion()`；**崩溃率随 Qt 运行库从 4%（2/50 @6.11.0）升到 ≈33%（1/3 @6.11.2）**，落点回到历史用例 `test_concurrent_subscribe`。**② 保活单例**：`pilotstd/ui/core/event_bus.py` 的 `reset()` 不再销毁 QObject（只清状态 + 世代号 + 有界排空）；删除 `_accepting`／`_drain_barrier`；契约改为「同一实例 + 状态清零」（`test_reset_creates_new_instance` → `test_reset_keeps_instance_and_clears_state`，不删除用例）。**本地**：崩溃点文件 20 轮全绿（每轮 19 passed @Qt 6.11.2）；全量 GUI 套件 1022 passed / EXIT=0。**③ 回归门**：`gui-race-probe` run `36431925613`（loops=50）→ **failures=2**（❌ 未通过：按用户裁定停止自行尝试方向 2／4，上报待裁） **验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.55 | 2026-09-27 | **EventBus `reset()` 改为「保活单例」——永不析构 QObject（第十二轮 R12-5 ②，用户裁定方向 1）**。**改动**：`pilotstd/ui/core/event_bus.py` —— ① `reset()` 只做「关门（`_resetting`）→ 清订阅者表 + `_generation += 1` → 有界排空 → 复位」，**不再 `cls._instance = None`、不再 `deleteLater()`**；② 删除实例级 `_accepting` 门闸（“退役实例”状态随销毁路径一并消失）与已无调用方的 `_drain_barrier` 槽；③ 新增**世代号** `_generation`：`publish()` 随事件入队世代号、`deliver(event, data, generation)` 丢弃陈旧世代的事件——用「逻辑重置」替代旧实现「换新实例」的隔离效果。**契约修正（用户指导）**：`reset()` 不再保证 `instance() is not old`（**该旧契约正是 use-after-free 缺陷本身**），改为保证 **`instance() is old` 且 `_subscribers == {}`**；用例 `test_reset_creates_new_instance` **不删除、只修正语义**（重命名为 `test_reset_keeps_instance_and_clears_state`，断言同一实例 + 状态清零），另补 `test_reset_is_idempotent_and_keeps_object_alive` 与 `test_publish_after_reset_with_stale_reference_is_discarded`。**禁止项遵守**：未删除/跳过 `test_publisher_thread_during_reset_does_not_raise`；未引入线程安全代理；未改与事件总线生命周期无关的代码。**本地实测**：`tests/gui/test_event_bus_integration.py` → **19 passed / 103s**。**同批证据（R12-5 ① 的连带发现）**：环境 pin 校正后的快检探针（Qt 运行库 **6.11.2**，run `36428298369`）在 **3 轮里第 2 轮即崩**（退出码 `-1073741819 = 0xC0000005`，`........` 后中断＝第 9 项 `TestThreadSafety::test_concurrent_subscribe`）——即**换到正确的 Qt 运行库后，崩溃率从 4%（2/50 @ Qt 6.11.0）升到 ≈33%（1/3 @ Qt 6.11.2），且落点回到历史崩溃用例**，证明方向 3 对复现能力至关重要。 |
| v1.54 | 2026-09-27 | **R4 探针环境 pin 校正（第十二轮 R12-5 ①）**。**口径纠正（自查发现）**：此前探针指纹只打印 `QT_VERSION_STR`——它是 PyQt6 的**编译期**常量（`PyQt6==6.11.0` → 恒为 `6.11.0`），因此 R12-4d 记的「实测 Qt 6.11.0」**并未反映实际加载的 Qt 运行库**；真身须看 `PyQt6.QtCore.qVersion()`（本地实测同为 6.11.2）。**改动**：`.github/workflows/gui-race-probe.yml` 的依赖安装步骤改为 `shell: pwsh` + **严格错误处理**（每个 pip 后 `if ($LASTEXITCODE -ne 0) { throw … }`——原先 PowerShell 默认不因非零退出码失败，正是它让 `pip install PyQt6==6.11.2`（**PyPI 上不存在该版本**，PyQt6 最新为 6.11.0）静默失败）；把该行换成 **`pip install "PyQt6-Qt6==6.11.2"`**（Qt 运行库真身）；并新增**指纹断言步骤**：打印 `python`／`QT_VERSION_STR(build)`／`qVersion(runtime)`／`PYQT_VERSION_STR` 并断言 **`qVersion() == '6.11.2'`** 且 `PYQT_VERSION_STR == '6.11.0'`，不满足即 `throw` 失败。与 `test-gui-unit`（`desktop/requirements-win.txt` 钉 `PyQt6==6.11.0`）保持同口径。**验证**：派发 3 轮探针确认「安装严格失败检测 + 指纹断言」通过（结果记入主簿 R12-5 ③）。 |
| v1.53 | 2026-09-27 | **R4 探针结果入账：R2 未完全覆盖根因，#34 维持 P6 并启动 R12-5（第十二轮 R12-4d）**。**工具**：`gui-race-probe.yml`（仅 `workflow_dispatch`；`windows-latest` + Python 3.12 + PyQt6 pin）循环跑 `tests/gui/test_event_bus_integration.py`。**实测**（run `36313158979`，sha `0404cea4` 含 R2）：**`loops=50 → failures=2`**（第 2、43 次），两次均 `..................F`（18 passed 后第 19 项失败）+ 退出码 **-1073741819 = 0xC0000005（STATUS_ACCESS_VIOLATION）**；单轮 ≈109s、整作业 ≈121 min。**失败落点**＝新增冒烟用例 `TestResetQuiescenceProtocol::test_publisher_thread_during_reset_does_not_raise`（工作线程首建单例 + 主线程并发 reset）→ **R2 的静止协议未覆盖该路径**。**环境指纹实测 Qt 6.11.0 / PyQt 6.11.0（pin 6.11.2 未生效）**，需在 R12-5 校正。**裁定（用户预设条件表第三行）**：❌ R2 未完全覆盖 → **#34 维持 P6 强制项，立即启动 R12-5 深挖**（候选：`reset()` 不再销毁实例／禁止非主线程首建 QObject／跨线程 `deleteLater` 与线程亲和性专项／必要时 ASan）；**回归门**＝`gui-race-probe` loops=50 → failures=0（当前 4%）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.52 | 2026-09-27 | **R2 验证数据入账（第十二轮 R12-4c）**。**本地**：`tests/gui/test_event_bus_integration.py` 连跑 **20 轮**，每轮 **19 passed / exit=0**（单轮 101.6~103.9s、累计 ≈34 分钟）→ **0 次 access violation**；**CI**：R12-4b 的 run `36313155232`（`0404cea4`）**13/13 作业 success（含 `test-gui-unit`）**；**R4 探针**：修复前（`a7c7e265`，30 轮）in_progress、修复后（`0404cea4`，50 轮）pending（同并发组串行），结果记入主簿 R12-4d。**#34 终局**待探针数据落定后裁定（候选：升级为「已修复（R2）＋ 继续观察」或维持「转已接受」并记 R2 为额外缓解）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.51 | 2026-09-27 | **#34 的 R2 静止协议落地（第十二轮 R12-4b，事件总线）**。**改动**：`pilotstd/ui/core/event_bus.py` —— ① 关门：类级 `_resetting` + 实例级 `_accepting=False`（`publish`／`subscribe`／`unsubscribe` 在 reset 窗口与退役实例上一律无副作用直接返回）；② 有界排空：仅当实例属本线程时 `processEvents()`，**移除无界 `BlockingQueuedConnection`**（实测其在“实例线程亲和性无事件循环”时永久挂住 teardown——R12-4 新冒烟用例暴露）；③ `deleteLater()` 延迟销毁，不同步析构 QObject；④ 复位 `_resetting`；并把 `publish()` 入队动作移入临界区（reset 拿锁即无 in-flight publish 入队）、`deliver()` 对退役实例直接丢弃。**受控用例 +6**（`tests/gui/test_event_bus_integration.py::TestResetQuiescenceProtocol`）；**本地实测 19 passed / 101s**（原 13 + 新 6，含 CI 曾失败的 `test_concurrent_subscribe`）。**R4 取证**：`gui-race-probe`（Windows + Python 3.12 + PyQt6 6.11.2）对修复前（`a7c7e265`）与修复后分别循环跑，结果记入主簿 R12-4c。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0（Ruff/Mypy/G-038 全 PASS，G-032 保持 13）。 |
| v1.50 | 2026-09-27 | **L1 触发式纳入 `.pyi/.pyw`（T-32 CLOSED）＋ R4 探针工作流立项（第十二轮 R12-4a）**。**T-32 修复**：`scripts/check_all.sh:303` 的 L1 触发式由 `^scripts/` 或 `.py$` 改为 **`^scripts/` 或 `.py[wi]?$`**（覆盖 `.py`／`.pyi`／`.pyw`），文案与注释同步；**双向受控验证**：修复后暂存 `pilotstd/_t32_probe.pyi`（142 字符行）→ L1 触发 → `E501` → `❌ [FAIL] L1 ruff check`（EXIT=1）；修复前同一探针可正常提交（R12-3b 的受控失败实验即借该缺口做到“不绕过钩子”）。**T-32 ✅ CLOSED** → 由「六、观察项」移入「一、已清理」。**R4 立项**：新增独立工作流 `.github/workflows/gui-race-probe.yml`（仅 `workflow_dispatch`，默认 loops=30）——`windows-latest` + **Python 3.12 + PyQt6==6.11.2**（与 `test-gui-unit` 同口径）循环跑 `tests/gui/test_event_bus_integration.py`，用于 #34 的 access violation 取证（修复前捕获／修复后 N 次 0 崩溃）；独立文件避免 `workflow_dispatch` 连带跑完整流水线。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；两个 workflow 文件均经 PyYAML 解析。 |
| v1.49 | 2026-09-27 | **方案 C 受控失败实证 + G 数据点 3 + #34 哨兵触发（第十二轮 R12-3b）**。**受控失败**（PR #8 一次性分支注入 `pilotstd/_r12_3_probe.pyi` 142 字符行，main 未受影响，用后关闭 PR + 删分支）：run `36310949966` **总时长 19.0s**（基线 828s，−97.7%），`lint-fast` failure 16.0s（`E501 Line too long (142 > 120)`），**下游 12 个作业全部 skipped** —— 方案 C 三条判据（快闸快失败／下游不启动／≤60s）全部达成。**G 数据点 3**：R12-3 的 run `36310444541` 首个作业启动 **+16.0s**（原始值超 ≤10s 阈值；同窗旧组对照 R12-1 `36309485009` +198s；门控落地后该指标已含 runner 分配与快闸时长两层）→ **收口判定待用户裁定**。**方案 C 绿灯代价实测**：快闸启动 +16.0s、时长 14.0s，下游首个作业 +32.0s（≈ +30s）。**取消语义再现**：R12-2／R12-2b 被后继同 ref 推送取消，旧组 R12-1 success 不受影响。**⚠️ #34 哨兵触发（T-26）**：同 run 的 `test-gui-unit` 报 `test_concurrent_subscribe FAILED` + `Windows fatal exception: access violation`（与历史逐行同构，R1 未拦住）→ 按 T-26 预先约定 **R2（`reset()` 静止协议）+ R4（CI/本地环境对齐复现）为第十二轮强制项**，计划见主簿 7.18。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；YAML/依赖图经 PyYAML 复核。 |
| v1.48 | 2026-09-27 | **新增 `lint-fast` 快闸作业并门控 9 个下游作业（第十二轮 R12-3，方案 C）**。**改动**：`.github/workflows/ci.yml` 新增 **`lint-fast`**（checkout `fetch-depth: 1` → `setup-python` 3.12+cache → `pip install ruff mypy` → `python scripts/check_g_038_legacy_errors.py`，**命令与范围零改动**），并给 `test-backend`／`test-gui-coverage`／`e2e-coverage`／`security-scan`／`test-frontend`／`test-e2e`／`frontend-e2e`／`test-gui-unit`／`repo-compliance` 共 **9 个作业**加 `needs: [lint-fast]`（保留各自原有依赖）；`version`→`docker`／`exe` 由原 `needs` 链**传递性**门控。**预期收益**：lint 失败 → 下游**根本不启动**，失败 run 时长 **828s → ≤60s**；绿灯路径代价 ≈ **+20s**（快闸自身时长）。**未改动**：G-038 脚本、ruff/mypy 范围、`repo-compliance` 内同名步骤（保留作纵深防御）、任何测试逻辑。**受控失败实验**：在一次性分支以 `.pyi` 长行触发（ruff 检查 `.pyi`，而本地 L1 触发式漏 `.pyi` → 无需 `--no-verify`），验证「快闸快速失败 + 下游 skipped + 主线不受影响」；该 L1 缺口另登记 `docs/technical-debt.md`「六、观察项」**T-32**。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；YAML 经 PyYAML 解析复核 `needs` 依赖图（13 作业）。 |
| v1.47 | 2026-09-27 | **方案 G 首个数据点入账 + `-rs` 覆盖全部 pytest 调用（第十二轮 R12-2b）**。**补充改动**：`-rs`（跳过明细）由 `test-backend` 一处扩到**全部 5 处** pytest 调用——`tests/`（test-backend）、`tests/gui/`（test-gui-coverage，xvfb 包裹）、`tests/e2e/`（e2e-coverage）、Windows GUI E2E（`tests/gui/`，参数 `-m e2e`）、test-gui-unit（`tests/gui/` 与 `tests/test_regression_architecture.py`）；复核脚本列出 **5/5 均含 `-rs`**。**G 首个数据点（R12-2 推送后实测）**：R12-2 的 run `36309693229`（组 `ci-cd-refs/heads/main`）**作业启动延迟中位 +2.0s**（2.0~4.0，n=7）；**同时间窗对照**旧组 run `36309485009`（R12-1，组 `ci-cd`）**中位 +198s**（197~257）→ 按 ref 分组已把新 run 与旧组 backlog 解耦（基线：未被挡 +3s／被挡中位 ≈300s／被挡比例 33%）。**T-28 ✅ CLOSED**（CI 实证：`test-backend` 日志输出 44 条 `SKIPPED [n] path:line: reason`，此前仅汇总行；用户裁定 1 行修复与 T-30 同批）→ 由「六、观察项」移入「一、已清理」。**路线确认**：R12-3＝方案 C（lint-fast + `needs` 门控）；D/E（缩短关键路径）挂后。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；YAML 经 PyYAML 解析（concurrency＝`ci-cd-${{ github.ref }}`／`True`）。 |
| v1.46 | 2026-09-27 | **CI 并发模型改为按 ref 单组 + 取消旧 run（第十二轮 R12-2，方案 G）＋ pytest 加 `-rs`（T-28）**。**改动**：`.github/workflows/ci.yml` 顶层 `concurrency` 由 `group: ci-cd` + `cancel-in-progress: false` 改为 **`group: ci-cd-${{ github.ref }}` + `cancel-in-progress: true`**（检查逻辑零变更）；`test-backend` 的 `Run backend tests` 步骤 pytest 命令加 **`-rs`**（跳过明细进日志，供 `tests/skip_census.py` 解析）。**依据（R12-1 归因，78 run）**：全局单组使 **26/78 = 33%** 的 run 被前一个 run 挡住（等待中位 ≈300s、最长 1340s），而 run 中位时长 828s（关键路径 `test-gui-unit` 467s）→ 连续推送必然互撞。**新模型**：① 同 ref 内新推送取消被取代的旧 run（排队≈0，代价＝旧 run 无完整结论，其提交由下一次 run 覆盖验证）；② 分支/PR 推送改用独立组，不再占用 main 槽位。**观察口径**：作业启动延迟（`job.started_at − run.run_started_at`）；基线＝未排队 +3s / 被挡中位 ≈300s，目标＝连续 3 次 run 中位 ≤10s，据此决定是否进 R12-3（方案 C）或 D/E。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；YAML 经 PyYAML 解析复核。 |
| v1.45 | 2026-09-27 | **第十二轮候选池立项 + T-30 排队归因（R12-1，纯只读分析，CI 零改动）**。**候选池**：用户批准 P0~P6 优先级（P0 T-30 CI 排队瓶颈／P1 T-29 8 处永久 skip／P2 T-28 CI pytest 缺 `-rs`／P3 T-27 新增文件检查盲区／P4 #32 中文状态值分阶段偿还／P5 #31 ConfigManager 交错写／P6 #34 竞态 R2+R4），登记于 `docs/technical-debt.md` 新增「〇 · 0.2 第十二轮候选池」。**T-30 归因（78 run 全量 + 10 run 关键路径）**：① **自串行**为主因——本仓库 `concurrency: group: ci-cd` + `cancel-in-progress: false` 使 **26/78 = 33%** 的 run 被前一个 run 挡住，等待 1~1340s（被挡中位 ≈300s）；② **runner 分配不是瓶颈**（未被挡时作业启动 +3s）；③ **放大因子是一次 run 太长**——run 中位 **828s**，关键路径 `test-gui-unit` **467s** → `version` 8s → `docker`/`exe` ≈176s；④ 「bump 提交产生额外 run」**证伪**（`GITHUB_TOKEN` 推送不触发 workflow，78 run 中 bump 类型 0 个）→ 新观察项 **T-31**。**方案对比 A~F 与推荐路线**（R12-2 先落“按 ref 单组 + cancel-in-progress”再观察）见主簿 7.15；本轮**未改任何 CI 配置**。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.44 | 2026-09-27 | **T-24 L3 落地：CI lint 步骤前移（第十一轮 R11-5，CI 效率优化条目）**。**改动**：`.github/workflows/ci.yml` 的 `repo-compliance` 作业中，`G-038 — 历史遗留错误清零（Ruff+Mypy+裸noqa）`**由末位前移到最前端**（紧跟 checkout）——检查逻辑、命令、范围一字未改，纯步骤顺序调整（PyYAML 解析复核顺序：checkout → G-038 → compliance → G-026/029 → Docs sync → Capabilities → G-030/032/033/037 → G-015）。**数据（11 次 run 实测）**：该步骤原在作业内 **+13s** 完成（其前面 10 个步骤合计仅 ~3s），前移后 ≈ **+12s** → 顺序收益 ≈ **1s**；对照组 `test-backend` 的 Ruff 步骤作业内 **+30~34s**（前置 `Install dependencies` 独占 23~29s）。**结论更正**：真正主导红灯暴露时间的是 **runner 排队**（11 次 run 作业启动相对 run 开始＝中位 **154s**、最长 **471s**，源于 `concurrency: group: ci-cd` + `cancel-in-progress: false` 使连续推送串行）；三次 E501 事故 run 的 lint 红灯本就在作业内 **+12~14s** 报出，“等 3 分钟”是排队而非步骤顺序。故 L3 的实质收益＝让 lint 成为作业内**首个**信号；真正的杠杆（并发组按 ref 拆分／下游重作业 `needs` 门控）登记 `docs/technical-debt.md`「六、观察项」**T-30**，挂第十二轮。**同批入账**：**T-20 ✅ CLOSED**（用户裁定方案 A：R11-4 实测证伪原假设 + 交付 fixture 基线/普查工具，0/43 需治理）→ 按本节纪律由「六」移入「一、已清理」；其剩余可治理项拆为 **T-29**（8 处永久 `@pytest.mark.skip`，可偿还候选、预估 ≤2 commit，挂第十二轮）；T-28 维持挂窗。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；推送后 `repo-compliance` 作业首个实质步骤即 G-038。 |
| v1.43 | 2026-09-27 | **T-20 口径更正 + fixture 基线（第十一轮 R11-4，纯新增测试资产）**。**实测三口径**：静态 `self.skipTest` **60 处 / 10 文件**（其中 43 处 `Fixture not found` 守卫）；本地运行期（`pytest tests/ -q -rs --ignore=tests/gui/`）**4290 passed / 14 skipped**（含 R11-4 新增 10 例）；CI 运行期（run `36306309371` 的 `test-backend`）**3997 passed / 44 skipped**。**更正**：43 个 fixture 守卫依赖的 15 个 fixture 文件**全部已入库**（`tests/fixtures/`）→ 运行期**一次也不触发**，「因缺 fixture 而跳过」= **0 处**；T-20 原「60 处会让跳过数长期偏高」是把**静态调用点**当成运行期跳过数（口径误用）。**本批只新增测试资产、不改既有测试逻辑、不删除/替换任何 skip**：`tests/fixture_baseline.py`（fixture 基线登记 15 项 + `uncovered_guards()` 守卫覆盖率判定）、`tests/skip_census.py`（运行期／静态双口径普查，按 fixture／random／platform／network／dependency／other 分类，`--json` 可机读）、配套受控测试 10 例（`tests/test_fixture_baseline.py` 5 + `tests/test_skip_census.py` 5）。**剩余可治理候选**：8 处 `@pytest.mark.skip`（`test_query_subsystem_snapshot.py` ×4 + tests/unit/query/engine/test_batch_dispatch.py ×4，依赖真实 HTTP／ThreadPoolExecutor／daemon 线程）→ 挂第十二轮；新登记 `docs/technical-debt.md`「六、观察项」**T-28**（CI pytest 未开 `-rs`，跳过明细无法从 CI 日志获得）。**验证**：新测试 10 passed；`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.42 | 2026-09-27 | **T-25 补丁之二（第十一轮 R11-3b）：遗漏补修 + 浅克隆根因**。**① 自曝遗漏**：R11-3 首次提交（`30de04e4`）因编辑工具在 CRLF 文件上锚点失配，**`.github/workflows/ci.yml` 的 YAML 修改未落盘**（重做时的补丁脚本只覆盖了两个 .py）；CI 日志自证——run `36306033918` 的步骤环境仍为 `DOCS_SYNC_RANGE: 409a5be1…92..`（右端为空）。**② 第二层根因**：回退候选 `origin/main...HEAD` 在推送 main 时因 `origin/main == HEAD` 恒空。**③ 第三层根因（本轮新查明）**：同一作业更早的 `.github/scripts/check-repo-compliance.sh` 执行 `git fetch origin main --depth=1`，**在 tip 建立浅边界**（`.git/shallow`）→ `HEAD~1` 不可用（实测 `fatal: Needed a single revision`）、`git log -n2` 只剩 1 条 → 兜底范围 `HEAD~1..HEAD` 亦失效。**修复**：`.github/workflows/ci.yml` 右端改 `${{ github.sha }}`；`check-repo-compliance.sh` 去掉 `--depth=1`（不再截断历史，行为等价——checkout 本已 `fetch-depth: 0`）；scripts/check_docs_sync.py（R16 改名为 check_module_doc_mappings.py） 与 `scripts/docs_sync_check.py` 新增 `_is_shallow_clone()`，浅克隆下必须声明“历史被截断”而非谎称“该范围无变更”。**验证（本地按 actions/checkout 流程端到端复刻浅克隆）**：右端为空 → 输出带浅克隆提示；**显式 `409a5be1..30de04e4` → 真实评估 8 个文件**（证明修复在浅克隆下有效）；受控测试 **23 passed**。**连带发现**：`check-repo-compliance.sh` 的“新增文件”检查在推送 main 时 `origin/<base>..HEAD` 恒空（白名单/黑名单从未生效）→ 登记 `docs/technical-debt.md`「六、观察项」**T-27**，挂第十二轮。**盲区谱系**：① G-040 受控测试不在本地门禁路径；② ruff/mypy 不在 `--fast`；③ `tests/` 受控测试路径缺口；④ 脚本名形近（T-25）；⑤ 环境变量取值陷阱（T-25）；⑥（同族，待修）范围恒空的新增文件检查（T-27）。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.41 | 2026-09-27 | **T-25 补丁：CI 范围取值陷阱（第十一轮 R11-3，第五个 CI 盲区实证）**。**事故**：`Docs sync check` 步骤的环境变量写成 `DOCS_SYNC_RANGE: ${{ github.event.before }}..${{ github.event.sha }}`，而 **push 事件载荷没有 `event.sha`**（正确为通用上下文 `github.sha`，push 时即本次推送 tip；push 专有字段是 `github.event.after`）→ 右端展开为空 → 该候选被脚本判为非法 → 回退 `origin/main...HEAD`；**推送到 main 时 `origin/main` 与 `HEAD` 指向同一提交、diff 恒空** → 步骤仍以 `PASS: 无变更文件` 空转，即 T-25 此前属“接线对了但范围算错”的半修。**实证**：GitHub 在步骤日志中直接打印该变量——run `36304263963`（`b2a8717c`）为 `DOCS_SYNC_RANGE: 27a39d6102c4d076a05f960100668acc08ef9c93..`（左端正确、右端为空）；本地以同形态复现出与 CI 逐字相同的 `变更来源: origin/main...HEAD（BASE_BRANCH=main）｜模式: 告警期` + `PASS: 无变更文件`。**修复**：① `.github/workflows/ci.yml` 右端改 `${{ github.sha }}`；② scripts/check_docs_sync.py（R16 改名为 check_module_doc_mappings.py） 与 `scripts/docs_sync_check.py` 的回退链新增“**候选必须确实含变更文件**”校验（**严格模式生效**，非严格模式保持旧行为以免本地误抓历史提交触发自动改文档）——空 diff 的候选继续回退到 `HEAD~1..HEAD`，全部为空时以“该范围无变更”显式说明收场，绝不静默通过；`--range` 硬指定不受该过滤影响。**受控验证**：右端为空 → 两脚本均回退 `HEAD~1..HEAD` 并输出真实判定；`--range 27a39d61..b2a8717c` → 正确报出 `docs/development.md` 未同步（工作流变更规则）且 EXIT=0（告警期）；`--strict-block` 语义未变。**反证**：新增 11 例受控测试（tests/test_check_docs_sync.py（R16 同名改名） 6 例 + `tests/test_docs_sync_check.py` 5 例），对修复前脚本 **6 failed**、修复后 **19 passed**。**盲区谱系（五个实证）**：① G-040 受控测试不在本地门禁路径；② ruff/mypy 不在 `--fast`（T-24）；③ `tests/` 受控测试路径缺口；④ 脚本名形近 → 接线错（T-25）；⑤ **本条的“环境变量取值陷阱 → 范围恒空 → 假绿”**。**连带**：T-16 观察计时器再次归零（自 R11-3 起重新计时）；`docs/governance/README.md` 索引版本 v1.41；能力矩阵按 AGENTS §七 重生成。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0。 |
| v1.40 | 2026-09-27 | **三债终局裁定（第十一轮 R11-2，纯文档；门禁逻辑零变更）**：#31／#32／#34 的**裁定书**逐条写入 `docs/technical-debt.md`「二、剩余台账」对应行（四要素：现状量化／偿还方案+成本／转已接受的代价／终局结论），判决＝**#31 [挂窗第十二轮]**、**#32 [挂窗第十二轮起分阶段偿还]**（附四阶段路线图 A~D，合计 7~12 commit、跨 ≥3 轮）、**#34 [转已接受+代价]**（保留 R1；哨兵＝复发 ≥1 次即当轮做 R2+R4）。**本轮只出裁定书、不做全量偿还**（用户指定），未改 `scripts/` 与 `.github/workflows/` 任何内容，故无门禁行为变化；本行仅登记**裁定过程**以留痕：① **取数方式**——#34 走 GitHub Actions API（`/actions/runs` 全量 73 run + 逐 run `/jobs`）、#31 走运行时打点 + pytest 插件探针、#32 走 AST + `tokenize` 口径，全部记入主簿「七、操作记录 **7.10**」；② **数据更正两处**——#32 容器定义点由“7 处”更正为 **9 处／5 个名字**（原探针未解包 `frozenset(...)`，漏计 EXPIRED_STATUSES／_EXCLUDED_FROM_OVERRIDE），#31 单位成本本轮复测 **4.28／4.27／4.28 ms**（每次恰 1.00 次构造 + 1.00 次 save）；③ **口径与观察项联动**——「〇 · 0.1 轮次口径」的当前轮次更新为**第十一轮（债务终局裁定轮）**，「六、观察项」新增 **T-26**（#34 复发哨兵：R1 后 14 run／`test-gui-unit` 14-14 success，基率 ≈1／40 下零复发概率 ≈70%，故不足以证明根除）。**G-031 联动**：本节仅记录裁定过程，**门禁规则与同步映射零变化**；`docs/governance/README.md` 索引版本同步 v1.40、能力矩阵按 AGENTS §七 重生成。**验证**：`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0；G-032 告警保持 13（无新增）；G-030 PASS。 |
| v1.39 | 2026-09-27 | **T-25：CI docs-sync 步骤"形近脚本接线事故"（第十一轮 R11-1）——第四个 CI 盲区实证**。**事故**：第十轮把 `ci.yml` 的 `Docs sync check` 步骤写成 `python scripts/check_docs_sync.py --strict`，而 `--range`/`--strict` 的实现全在 **`scripts/docs_sync_check.py`**（两脚本仅差 `check_` 前缀）→ ① CI **从未执行过严格模式**；② 被实际执行的 check_docs_sync.py 当时只做 `git diff --name-only origin/<base>..HEAD`——**推送到 main 时 `origin/main` 与 `HEAD` 相同、浅克隆下甚至取不到** → 恒 `[docs-compliance] PASS: 无变更文件`、恒 `exit 0`。**证据**：6/6 run 该步骤 `success` 且日志仅一行 `[docs-compliance] PASS: 无变更文件`（run `36301687032` 第 223 行）；`git grep docs-compliance` 只命中 check_docs_sync.py。**后果**：T-16 的 6 次「告警期观察」**全部无效**（观察对象为空转脚本）→ 观察计时**归零重置**，自 R11-1 起重新计时。**修复**：① `ci.yml` 该步骤**依次跑两个脚本**（`set -e`）：`docs_sync_check.py --strict` + `check_docs_sync.py --strict`（后者 5 条映射**比 G-031 更宽**，含 `pilotstd/query/`、`pilotstd/ui/`，不可删）；② check_docs_sync.py 补齐**范围回退链**（`--range` → `DOCS_SYNC_RANGE` → `--base`/`BASE_BRANCH`（`origin/<base>...HEAD`）→ `origin/main...HEAD` → `HEAD~1..HEAD`；三点范围与全 0 SHA 正确处理）与**告警期语义**——未同步时打印 `[docs-compliance] WARN(告警期) … **未阻断**（exit 0）`（**绝不静默 PASS**），`--strict-block` 才 `exit 1`，不带标志保持历史行为（`exit 1`）；③ 修其自身缺陷：Windows GBK 控制台打印 `❌` 抛 `UnicodeEncodeError` → **假性 exit 1**（本该 exit 0 的告警期），已补 `sys.stdout.reconfigure(encoding="utf-8")`。**受控验证**：`--range a7225689^..a7225689`（历史提交：改 `pilotstd/ui/` 未同步 `ui.md`）→ 告警期 WARN + **EXIT=0**；`--strict-block` **EXIT=1**；无标志 **EXIT=1**；干净范围 PASS + EXIT=0。**盲区谱系（四个实证）**：① G-040 受控测试不在本地门禁路径；② ruff/mypy 不在 `--fast`（T-24）；③ `tests/` 受控测试路径缺口；④ **本条的"脚本名形近 → 接线错、步骤空转"**。 |
| v1.38 | 2026-09-27 | **T-24 裁定入账 + L1/L2 落地（`.py` 变更的快速 lint）**：**用户裁定**——`.py` 变更的强制本地门禁目标不变（`--deep` 的 ruff/mypy/G-038），但须解决耗时，故**分层落地**。**根因回指**：ruff/mypy 只在 `--deep` 与 CI 执行、不在 `--fast`（pre-commit 口径），且各机 PATH 不保证存在 → 归档件 4 行 E501 未被本地拦住，CI 连红三次（`36300484047`/`36301031251`/`36301267833`）并连带 skipped 4 个 job。**L1 ✅ 已落地（即时生效）**：`check_all.sh --fast` 新增 `run_lint_fast()`——**暂存变更含 `scripts/` 或 `*.py`** 时自动增跑 `ruff check pilotstd/ docker/ tests/ scripts/` 与 `mypy pilotstd/ docker/ --follow-imports=skip --ignore-missing-imports`（**与 G-038 完全同口径**，实测 <5s）；工具缺失时**降级 WARN 不阻断**（沿"各机 PATH 不一致"的既有理由）。**L2 ✅ 已落地**：新增 `--with-lint` 标志显式强制增跑（不依赖暂存区，供自查）。**L3 ⏳ 挂第十一轮**：评估把 G-038 的 ruff/mypy 提前到 CI `repo-compliance` job 最前端（`test-backend` 之前），让红灯 1 分钟内暴露；需单独 PR（属 CI job 结构变更）。**受控反证**：向 `scripts/` 注入一条 150 字符行并暂存 → `--fast` 输出 `E501 Line too long (150 > 120)` 且 `❌ [FAIL] L1 ruff check`、EXIT=1（即 L1 能复现并拦住本次事故根因）。**自证（用户要求）**：改完钩子口径后跑 `check_all.sh --deep` → EXIT=0（Ruff/Mypy/Vulture/G-038/Schema 全 PASS），钩子自身通过 ruff/mypy。 |
| v1.37 | 2026-09-27 | **第十轮 CI 事故修复（E501 / G-038）**：`scripts/update_docs.archived.py`（T-15 归档件）头部"各函数替代方案"原写成 **Markdown 表格**，其中 4 行超过 ruff `line-length=120`（实测 362 / 256 / 201 / 185 字符）→ CI 的 **`test-backend`「Ruff check (blocking) — G-038」** 与 **`repo-compliance`「G-038 历史遗留错误清零」** 双双失败，并连带 skipped `docker`/`exe`/`version`/`test-gui-coverage`（run `36300484047` / sha `e94f8ddb`；run `36301031251` / sha `73a35ed5` 同因）。**修复**：该表格改为**按 ≤120 列宽折行的清单**（内容零删减，仅排版变化）。**验证（CI 同口径本地复跑）**：`python -m ruff check pilotstd/ docker/ tests/ scripts/` → All checks passed；`python scripts/check_g_038_legacy_errors.py` → ✅ Ruff/Mypy 零错误；`check_all.sh --fast --guards --local` 与 **`--deep`**（含 Ruff/Mypy/Vulture/G-038/Schema 一致性）均 EXIT=0。**流程补记（同类缺口第二实例）**：ruff/mypy 只在 `--deep` 与 CI 中执行、不在 pre-commit 的 `--fast` 口径内——本轮 T-16 观察项已记录"CI 独有检查不在本地门禁路径"这一类缺口，本次为其**实证第二例**，故改脚本类提交应增跑 `check_all.sh --deep`。 |
| v1.36 | 2026-09-27 | **T-22 章节编号收敛 + 本轮收尾入账（第十轮第五批，纯文档）**：① **技术债主簿编号收敛**——「六-B、观察项」→ **「六、观察项」**、「八、操作记录」→ **「七、操作记录」**（含其 `8.x` → `7.x` 八个子节），消除"六-B → 八"空档；**全库引用同步**：本文件 v1.31/v1.33 行（原"刻意保留不改名"的说明改注"已在 v1.36 收敛"）、归档存根 `docs/architecture/technical-debt-registry.archived.md` 的内容去向表、`docs/ci-lessons.md:217`；所有历史提及一律加「编号收敛前为…」限定（残留检查：`git grep 六-B` 仅剩 **4 处**、`git grep 八、操作记录` 仅剩 **2 处**，**全部为带限定的历史叙述**）。② **本轮收尾入账（主簿）**：已清理补登 **T-14**（删死脚本 check_docs_sync.sh）/ **T-15**（归档 update_docs.py → `update_docs.archived.py`）/ **T-17**（G-032/G-033 排除 `*.archived.*`）/ **T-19**（删两个空章节）——按用户裁定用「根因 + 处置 + 验证 commit」三要素，不填窗口与代价（注：两个删除/归档前的路径此处不加反引号，以免触发 G-032 交叉引用告警）；观察项新增 **T-16**（`docs_sync_check.py` 严格模式**告警期**：切换阻断条件 = 连续 3~5 次提交误报为 0，切换方式 = `ci.yml` 中 `--strict` → `--strict-block`）/ **T-20**（`tests/` 运行期 `self.skipTest` 60 处 → 挂第十一轮）/ **T-21**（本地 `vitest` 偶发汇总全绿但 exit=1 → 挂起观察，复发时保存完整日志）。③ 连带 `docs/governance/README.md` 索引版本与能力矩阵重生成。**验证**：`check_all.sh --fast --guards --local` EXIT=0；G-032 保持 **13 warning 无新增**；G-031 两条映射 OK。 |
| v1.35 | 2026-09-27 | **T-15 归档 update_docs.py + T-17 归档件排除（第十轮）**。① **T-15**：scripts/update_docs.py（**归档前路径，不加反引号以免 G-032 交叉引用告警**）→ **`git mv` 为 `scripts/update_docs.archived.py`**（**停止维护**，头部注释列出五个函数各自的现行承担者与历史取回方式）。依据：**全库 0 调用点**（`git grep update_docs` 排除自身打印后仅剩文档叙述；不在 `.husky/pre-commit`、`check_all.sh` 任何模式、CI 任何步骤）；五个功能已被取代——测试数同步 → `scripts/generate_status_metrics.py`（写 STATUS.md AUTO-METRICS 区块）+ G-032 维度4；聚合器描述 → `pilotstd/core/notification/aggregate_buffer.py` 常量 + `docs/architecture/modules/core.md`（G-031）；技术债条目 → **T-02 已惰性化**（旧簿归档、主簿人工维护）；模块清单 → 目标文档自身 2026-08-19 即 ARCHIVED，现由 `docs/architecture/modules/*` + G-030/G-031/G-037 承担；自动 `git add` → 废弃。连带更正两处过时指针（`docs/DOCUMENTATION_MAP.md`、`docs/archive/specs/模块与功能清单.md` 头部"生成脚本仍引用"）。② **T-17（预防性加固）**：`check_g_032_doc_health.py` 与 `check_g_033_adr_integrity.py` 新增统一的 `is_archived()`（文件名含 `.archived.` 即归档件）——G-032 的**维度2 人工层新鲜度**与**维度3 交叉引用**跳过归档件（归档件 mtime 必然落后、内部链接可能指向历史路径，检查只产生无行动价值的噪音）；G-033 的**架构变更文件**列表排除归档件。**受控反证**：`is_architecture_change("docs/architecture/technical-debt-registry.archived.md")=True` 而 `is_archived(...)=True` → 计入=False；对照 `docs/architecture/modules/core.md` 与 `scripts/check_g_032_doc_health.py` 均仍计入=True（**未过度排除**）。**验证**：`check_all.sh --fast --guards --local` EXIT=0；G-032 告警 **13 个（无新增）**；G-033 实跑"无架构变更，跳过检查"、EXIT=0；`python -c ast.parse` 三个改动脚本语法 OK。 |
| v1.34 | 2026-09-27 | **T-16：docs_sync_check 严格模式告警期（第十轮）**。**深挖结论（原判断需加强）**：该脚本此前**不仅 CI 空转，而且 8 条触发规则全部是死代码**——`_match_trigger_rules` 用字典字面量做 arity 分派（`{3: fn(a,b,c), 2: fn(a,b), 1: fn(a)}.get(n)`），Python **先求值三个调用**，参数个数不符者抛 TypeError 被 `except` 吞掉（对照实验：旧写法 8/8 规则 TypeError；新写法 2 条规则正常触发）；叠加 ① 只读 `git diff --cached`（CI 全新检出恒空 → `无暂存区变更，跳过`）、② `main()` 所有路径 `return 0`（永不阻断）、③ 设计动作是调用 `claude` CLI 自动改文档（`AUTO_FIX_DOCS` 默认 true）。**本次改动**：① **修复 arity 分派**（按 arity 只调一次，不再吞异常）；② **变更来源回退链**：`--range A..B` → 环境变量 `DOCS_SYNC_RANGE` → `--base`/`BASE_BRANCH`（`origin/<ref>...HEAD`）→ 暂存区（本地默认，保持旧行为）→ `origin/main...HEAD` → `HEAD~1..HEAD`；三点范围与全 0 SHA（新分支）均正确判定为无效并回退；③ **严格模式**：`--strict` 只判定、**不改文档**（强制 `auto_fix=False`，满足 CI 离线前提），对 `in_repo=True` 目标未同批更新时逐条列出并 **仍 exit 0（告警期）**；`--strict-block` 才 exit 1；④ **CI 接线**：`ci.yml` 的 `Docs sync check` 步骤改为 `--strict` + `AUTO_FIX_DOCS=false` + `DOCS_SYNC_RANGE=${{ github.event.before }}..${{ github.event.sha }}`（PR 场景回退 `BASE_BRANCH`）。**告警期→阻断期**：观察若干次提交误报为 0 后，把该步骤的 `--strict` 改为 `--strict-block`（一行）即可开启阻断。**验证**：`--strict --range 5b859064..71e70054` 正确报出 `CHANGELOG.md`（feat: 规则、in_repo）而 exit 0；同范围 `--strict-block` **exit 1**；无参数默认回退 `origin/main...HEAD` 且"无变更，跳过" exit 0；新增受控测试 `tests/test_docs_sync_check.py`（**8 例**：arity 分派回归守卫 / 源码+feat 规则触发 / in_repo 标记 / 已同批更新则跳过 / 参数解析 / 二点三点范围切分 / 非法范围拒绝 / `--help`），修复前该文件必失败。 |
| v1.33 | 2026-09-27 | **P1 清理（第十轮，T-19 + T-14）**：① **删除死脚本 scripts/check_docs_sync.sh**（归档前路径，**不加反引号以免 G-032 交叉引用告警**）——该脚本自述"渐进式部署，仅提醒不阻断"、**全库 0 调用点**（`git grep check_docs_sync` 排除自身后无命中；未被 `check_all.sh` 任何模式与 CI 任何步骤调用），其"源路径 → 文档"提醒映射功能已由 CI 侧的 check_docs_sync.py 覆盖；本文件 v1.31 行内对它的引用同步去除反引号（原文保留说明其历史作用）。② **技术债文档删除两个空章节**「六、待决策」「七、清理项」（**旧编号**，两节已删除；唯一内容已于同轮移入「五 · 归档并入」与「一、已清理」），**「六-B、观察项」标签当批刻意保留不改名**（被本文件 v1.31 行、归档存根与主簿共 11 处历史引用）；该标签已在 **v1.36（T-22）** 统一收敛为「六、观察项」。**验证**：`check_all.sh --fast --guards --local` EXIT=0；G-032 告警数不变（13，无新增）；git grep 该脚本名全库 0 命中（仅本行以非反引号形式叙述其删除）。 |
| v1.32 | 2026-09-27 | **G-030 候选路径去幽灵（第十轮·架构优化与债务清算轮，T-13）**：`scripts/check_g_030_tech_debt.py` 的 `DEBT_REGISTER_PATHS` **删除** docs/governance/tech-debt-register.md（归档前候选路径，**此处不加反引号以免触发 G-032 交叉引用告警**）——该路径经 git log --all 核实**从未在仓库中存在过**（注释"存在任一即可"使门禁未因此失败，属脚本卫生缺陷）；候选现为**唯一一份** `docs/technical-debt.md`（SSOT，同轮确立）。脚本 docstring 同步改写（记录删除原因与核查方式）。**验证**：`python scripts/check_g_030_tech_debt.py` 仍 PASS（"未检测到新增技术债标记"），失败分支的提示文案随候选列表自动收敛为单一登记簿；`git grep tech-debt-register` 全库仅剩「文档说明性提及」2 处（本行与主簿变更记录），无功能性引用。**同批联动**：`docs/governance/README.md` 索引版本 v1.30 → v1.32、`docs/governance/capabilities_registry.md` 重生成（AGENTS §七）、`docs/technical-debt.md` 登记 T-12 的三条（AppLayout 兜底删除 / Tech-Debt #8 编号悬空补登 / 2 类代码 TODO 观察项），并同步 `web/src/components/AppLayout.vue`（删兜底 + 过期 TODO）与 `AppLayout.test.ts`（fixture 补 meta）。 |
| v1.31 | 2026-09-27 | **技术债数据源唯一化（第十轮·架构优化与债务清算轮，T-01/T-02）**：旧登记簿 docs/architecture/technical-debt-registry.md（归档前路径，**不再以反引号引用以免 G-032 交叉引用告警**）**废止并 `git mv` 归档**为 `docs/architecture/technical-debt-registry.archived.md`（归档存根仅保留归档原因 + 内容去向表 + `git show ba9af616:…` 历史取回方式），技术债**唯一数据源＝`docs/technical-debt.md`**。① **归档判定依据（实测）**：旧簿「六、G-010 警告基线（Backlog，9 文件）」与实测不符——`check_g_010_code_size.py` 现为**警告档 3 个 / 阻断档 0 个**（旧簿列的 6 个 >450 文件已被第八轮拆分）；且旧簿与主簿各自一套编号、需手工互指（原文"本登记簿编号 #21 = docs/technical-debt.md 第二节 #15"）。② **内容按"有价值即并入、过期即废弃"逐节处理**：13 条已跳过测试明细 → 主簿「四」；#6 JWT_SECRET、#7 内存会话存储 → 主簿「五」#6/#7；#6 WebSocket 广播无用户级路由 → 主簿「五」#8；#3 `_batch.py` 溢出部分内联、#4 迁移链顺序依赖 → 主簿「六、观察项」（编号收敛前为「六-B」；标注"并入留痕、无新增行动"）；`test_migration_runs_pending` patch 路径、PyInstaller `_SafeStream` 回退 → 主簿「一」；旧簿「四、Mypy 豁免项」→ 主簿「一」并**判定作废**（其"mypy 不阻断 pre-commit / `--no-verify`"与 G-038 + P-104 冲突）；「五、处理流程图」与「四、已跳过的环境依赖（`pytest-asyncio`，实测 `tests/test_health.py` 已无 async 测试且未在任何 requirements 声明）」废弃。③ **门禁脚本联动（G-031 同步点）**：`scripts/docs_sync_check.py` 的触发规则「架构模式变化（Handler/Mixin）」目标由旧簿**改指 `docs/technical-debt.md`**（保持"Handler/Mixin 变化须同步技术债登记"的规则意图），其 `prompts` 键名同步改为 `technical-debt.md`；`scripts/update_docs.py::update_tech_debt_entries` 目标改为归档文件并注明**惰性空操作**（正则不再匹配 → 恒 False，不会复活第二数据源）。④ **轮次口径立项**：主簿新增「〇、0.1 轮次口径」——**当前＝第十轮（架构优化与债务清算轮）**，自 v0.110.0 起算至 P0/P1 清零或降级为止；#31/#32 窗口"最迟第十轮"＝**本轮到期**，#34 的"第十轮最终判断"同步适用；**后续轮次一律按季度或大版本号（如 v0.120.0）表述，禁止"第 N 轮"无锚点写法**。⑤ **全库引用清理**：`git grep technical-debt-registry` 的 21 处引用全部处理（角色/索引类 12 处改指主簿；历史快照类 4 处改指 `.archived`；脚本 3 处见③；主簿自身 2 处改为归档说明）。 || v1.30 | 2026-09-27 | **批 6 登录/注册/收藏/通用 i18n 化（16 文件 83 行）→ 存量 83 → 0（基线清零，i18n 主线收尾）**：清零 `FavoritesView` 19、`RegisterView` 10、`RouteDebugPanel` 9、`BackupView` 6、`LoginView` 5、`LogBar` 5、`TableLoadFooter` 5、`QueryHistory` 4、`StandardTable` 4、`SystemResources` 4、`useFavorite` 3、`UnifiedFilterBar` 3、`api/http` 2、`router` 2、`useQueryAdapters` 1、`LegacyRedirect` 1。① **`router.ts` 两处中文 `meta.title` 兜底删除**：`/announce/:source/:announceNo` → `titleKey: 'announce.detail.route_title'`、`/announce/:announceNo` → `titleKey: 'legacy.redirecting'`——复用既有 `titleKey` 机制（不新造），删前 `git grep meta.title` 确认消费方只有 `AppLayout`（`r.meta.titleKey ? t(...) : r.meta.title`）与 `QuickActionsCard`，且这两条路由均非 `showInSidebar`/`showInQuickActions`。② **模块级表存 key**：`FavoritesView.typeTabs` → `labelKey`、`STD_TYPE_LABEL` → **`STD_TYPE_LABEL_KEY`**（值改为 key）、`UnifiedFilterBar.types` → `labelKey`（模板 `{{ t(type.labelKey) }}`），理由同批 2/5：模块作用域只能求值一次 `t()`。③ **非组件模块走 `i18n.global.t`**（批 4 建的实例）：`api/http.ts` 断网/超时提示、`useQueryAdapters.ts` 站点列表失败、`useFavorite.ts` 收藏 toast 与「操作失败 ({code})」。④ **复用**：`login.password`（10 个新键中唯一逐字同值者，复用既有键而非另建）。⑤ **未复用（声明为后续合并候选）**：新 `announce.type_long.{gb,hb,db}`（「国家标准公告/行业标准公告/地方标准公告」）与既有 `dashboard.announce_adapter.type.{gb,hb,db}` **值完全相同**，但前者是筛选条类型名、后者是公告适配器统计域，按“不为复用而扭曲语义”新建。⑥ **C-2/B 类豁免零改动**：`api/http.ts` 的 `['未登录','认证失败','会话已过期']` 判定、`QueryHistory.vue` 的 `r.status === '现行'`、`LoginView`/`useFavorite`/`useQueryAdapters` 的 `console.warn` 行全部保持原样。**三语**：12 个新顶层命名空间 + `login` 4 键 + `announce.type_long.*` 3 键 + `announce.detail.route_title`，叶子键 **772 → 860**，`check_i18n_key_count.py` 三语对齐 PASS。**受控测试**：新增 `views/CommonI18n.test.ts`（6 例，覆盖原本无测试文件的 `RegisterView`/`RouteDebugPanel`/`TableLoadFooter`/`UnifiedFilterBar`/`LegacyRedirect` + `router.ts` 的 titleKey 三语可解析且无 `meta.title` 兜底）；6 个既有测试文件（`LoginView`/`BackupView`/`QueryHistory`/`SystemResources`/`LogBar`/`StandardTable`）补 i18n 插件（原先不带 messages 挂载，组件内 `useI18n()` 会抛 `Need to install with app.use`）+ 语言切换断言；`FavoritesView.test.ts`/`useFavorite.test.ts`/`http.test.ts` 各补 1 例切换（后两者验 `i18n.global.locale` 切换后 toast/提示语跟随）。前端 **41 文件 / 297 测试全绿**，`vue-tsc` 0 错误。**G-010 复核**：警告文件数与批前同为 **3 个、无新增**（`AppLayout` 434 / `NotificationConfig` 438 / `_migrate_v16_v49.py` 438，三者均未被本批触及）；16 文件有效行合计 +29（`useFavorite` +4，`api/http` +1，`FavoritesView`/`router` +0，其余各 +2），最大增幅 4，无文件逼近 490。**过程事故（已闭环，提交前发现）**：批量替换脚本再次触发 PowerShell 数组塌缩，`useQueryAdapters.ts`（`e`→`r`）与 `LegacyRedirect.vue`（`<`→`p`）被误改，`git diff` 复核时发现并 `git checkout --` 还原后用 edit 工具重做；全库 corruption 扫描（逐文件 `<` 计数比对 HEAD）0 命中。**观察项（本批未处理，留待技术债复核）**：本地自定义规则 `custom/no-raw-i18n-key` 对「表里存 key、渲染期 t()」这一既有模式**误报**——`HEAD` 上 `useDashboard.ts`(13)/`themes.ts`(4)/`TaskView.vue`(5)/`QuickActionsCard.vue`(6) 共 28 处已存在同类报错，本批按同模式新增 `FavoritesView`(5)/`UnifiedFilterBar`(3)；该规则**不在 `check_all.sh` 与 CI 任何 job 中执行**（`.lintstagedrc.mjs` 未被 `.husky/pre-commit` 调用，钩子只跑 `check_all.sh --fast --guards --local`），故不影响门禁与 CI 结果，是否修规则（放行对象字面量中的 `labelKey`/`titleKey`）留待决策。 || v1.29 | 2026-09-27 | **批 5 仪表板/布局 i18n 化（15 文件 93 行）→ 存量 176 → 83**：清零 `AppLayout` 7、`AppHeader` 4、`AppSidebar` 2、`useDashboard` 9、9 个 widget（11/9/9/9/8/7/5/6/4）+ `PlaceholderWidget` 2 + `StatsCard` 1。① **模块级表改 `labelKey`**：`useDashboard.ts` 的 `CARD_REGISTRY` 由 `label`/`zhName` 改为 **`labelKey`/`titleKey`**（存 key、渲染期翻译），三处消费方同批跟随——`AppLayout` 悬浮菜单 `t(card.labelKey)`、`HomeView` 改传 `:title-key`、`AdapterStatusQueryCard` 的 prop 由 `zhName` 改 `titleKey` 并 `t(props.titleKey || 'dashboard.card.queryAdapterTitle')`。② **`QuickActionsCard` 的两套来源统一**：路由 meta 派生项原本在 computed 里就地 `t()` 出 `label`，静态兜底项则写死中文——现统一为 `labelKey`（路由项取 `meta.titleKey`，静态项取常量 key），模板 `a.labelKey ? t(a.labelKey) : a.label`；顺带 −5 有效行。③ **复用**：`common.no_data`（2 处「暂无数据」逐字一致）、`nav.task/organize/pending/announce`（快捷操作 4 个导航目的地名与侧边栏同源，属同一导航目标，长时一致优于另建）；`dashboard.common.normal` 一处收口 3 个「正常」。④ **未复用**：`home.current/expired/pending/upcoming` **已复用**（标准库构成图例与首页统计同语义同值）；`dashboard.common.loading`（'加载中...' 带省略号，与 `common.loading` '加载中' 不一致）新建。**G-010 复核**：警告文件数与批前同为 **3 个、无新增**；`AppLayout.vue` 434 → **434（+0，改动行中性）**，距 490 仍有 56 行余量；`QuickActionsCard` 149 → 144（−5），其余 +2（i18n import + 解构）。**过程事故（已闭环）**：批量替换脚本一处 PowerShell 数组塌缩导致 `StatsCard.vue` 内 `<` 被误替换为 `s`，**提交前**发现并 `git checkout --` 还原后改用 edit 工具重做，全库 `sspan` 残留为 0。受控测试：新增 `views/DashboardI18n.test.ts`（13 例，覆盖原本无测试文件的 12 个组件；含 `StatsCard` 的「不出现 key 回显」断言）+ `AppLayout` 补 1 例切换；前端 40 文件 / 282 测试全绿。 |
| v1.28 | 2026-09-27 | **批 4 公告/标准状态 i18n 化（4 文件 72 行）→ 存量 248 → 176**：清零 `StandardsStatusView` 24、`AnnounceDetail` 20、`composables/useAnnounceDetail` 18、`AnnounceView` 10。① **非组件模块首次落地**：**新建 `web/src/i18n.ts`** 把全局 i18n 实例从 `main.ts` 抽出（`main.ts` 有效行 123 → 107，`app.use(i18n)` 与 locale watch 不变），composable 内用 `i18n.global.t` 读 **toast** 文案（一次性、无需响应式）；而**模板渲染用的状态标签改为返回 key**（`parseStatusLabel` → `parseStatusLabelKey`、`parseButtonLabel` → `parseButtonLabelKey`、`statusLabel` → `statusLabelKey`），由组件 `t()` 翻译——因为 `i18n.global` 在单测里是**另一个实例**（各测试自建 createI18n），返回 key 才能既响应式又可测。② **`announce.type.*` 判定为不可复用**：现有值是「国家公告/行业公告/地方公告/其他公告」（`RecentAnnounceCard` 用），而本批需要的是页面/字段/列名（「公告」「标准清单」「发布日期」…）与统计缩写「国标/行标/地标」——文案不一致，新建 `announce.view.*` / `announce.detail.*`。③ **C-2**（决策 2：只豁免）：`StandardsStatusView` 筛选项的 3 个 `value`（`'现行'`/`'已废止'`/`'未知'`）是**提交给后端的查询参数**，只有 `label` 走 i18n，value 加 `i18n-allow`；`statusSeverity()` 的 3 行既有豁免未动。④ **循环变量遮蔽 `t` 复查**：4 文件均无。**G-010 复核**：警告文件数与批前同为 **3 个、无新增**；4 文件有效行各 +2（`useAnnounceDetail` +10：`t` 包装 + key 映射注释）。受控测试：新增 `views/AnnounceStandardsI18n.test.ts`（3 例：StandardsStatusView 切换 + AnnounceDetail 字段标签切换 + composable 的 labelKey 经 `t()` 翻译无 key 回显；`useIncrementalScroll` 与 `useAnnounceDetail` 按需 mock）+ `AnnounceView` 补 1 例切换；**动态拼接 key 自检**：`parse_status.*` / `btn_*` / `record_status.*` 共 12 个 key 三语齐全（静态探针 + 专用探针双查）；前端 39 文件 / 268 测试全绿。 |
| v1.27 | 2026-09-27 | **批 3 任务/下载/整理 i18n 化（8 文件 140 行）+ `settings.tasks` 键迁移 → 存量 388 → 248**：① **键迁移**（独立 commit）：`settings.tasks.save/saved` → 批 2 已建的通用键 `settings.save_config` / `settings.saved`，删除 tasks 域重复（`SettingsTabSchedule.vue` 2 处调用点；`git grep settings\.tasks\.save` 零残留），叶子键 471 → 469。② **8 文件清零**：`TaskView` 42、`TaskManager` 35、`DownloadImport` 15、`OrganizeView` 14、`PendingView` 11、`QualityView` 10、`SchedulerStatus` 9、`DownloadQueue` 4。**模块级字面量**：`TaskView` 的步骤表 `StepState.label` → **`labelKey`**（模板 `step.labelKey ? t(step.labelKey) : step.label` 回退，兼容 localStorage 里**旧版运行记录**只有 `label` 的情形，避免老数据取不到 key）；`TaskManager` 的状态/步骤映射改 `t()` + `computed`（`statusOptions`）。**复用既有 key（实测确认）**：`pending.importResult/importEmpty/importFailed` 与 `PendingView` 三行文案**逐字一致**，直接复用（这 3 个 key 此前三语已定义但**全库无引用**，本批首次落地）；`task.step.*` 被 `TaskView` 与 `TaskManager` 共用。**未复用**：`download.status.*`（值为「已入队/下载中/归档中/已归档…」，与本批的步骤/任务状态语义不同）、`download.import*`/`normalize.load*`（文案分别是「已导入 {n} 条可下载标准」「已加载 {n} 条查询结果」，8 文件中无此文案）、`action.scan_index`（「扫描索引」未出现）——均按"不为复用而扭曲语义"新建。**循环变量遮蔽 `t` 复查**：8 文件均无 `v-for="t in …"` 遮蔽（批 2 的 `SettingsTabAppearanceMixed` 是唯一一处，已在批 2 改名）。**G-010 复核**：警告文件数与批前同为 **3 个、无新增**；8 文件有效行各 +2/+3（import + 解构），`TaskView.vue` 397 → **399**（距 400 仅 1 行但**未越线**，故无新增警告）。受控测试：新增 `views/TaskDomainI18n.test.ts`（4 例，覆盖原本无测试文件的 TaskManager/DownloadImport/OrganizeView/PendingView）+ `TaskView`/`QualityView`/`SchedulerStatus`/`DownloadQueue` 各补 1 例切换；同时给这 4 个既有测试补 i18n 插件（否则 `useI18n()` 直接抛错）；前端 38 文件 / 264 测试全绿。 |
| v1.26 | 2026-09-27 | **批 2 设置页 i18n 化（14 文件 239 行）+ 通知事件名统一 → 存量 627 → 388**：① **事件名统一**（批 1 遗留决策，用户选 A）：同一后端事件的显示名在两页措辞不同（6 处），现合并为单一命名空间 `notification.event.<type>`（36 项，取配置页措辞），删除 `notification.config.event.*` 与 `notification.logs.event.*`（不留别名）；两处 `eventLabel()` 的派生 key 与 `t()` 守卫不变。② **设置页 14 文件清零**：`SettingsTabUsers/Token/Validity/Circuit/System`、`SettingsView`、`ValidityConfig`、`WechatTrustIP`、`FileMonitor`、`CacheManager`、`SettingsTabSchema`、`SettingsTabAppearanceMixed`、`DynamicSettingField`、`config/themes.ts`。**模块级字面量按 `router.ts` 的 `titleKey` 机制改**：`ThemeConfig.label` → **`labelKey`**（存 key、渲染期翻译；`SettingsTabSchema` 的 `LABELS` 同样改 `LABEL_KEYS` + computed），避免模块作用域 t() 只求值一次。**复用既有 key**：`common.cancel` / `common.save` / `common.saved` / `common.save_failed` / **`date.weekday.prefix` + `date.weekday.short.*`**（`ValidityConfig` 的周几词表直接复用，不再自造「周一…周日」）；新增 `settings.saved`（配置已保存）/`settings.save_config`（保存配置）两个 settings 域通用键。**C-2 处理**（决策 2：只豁免）：`WechatTrustIP.vue` 第 173 行（`current_ip !== '未知'`）保持既有 `i18n-allow` 不动；本批**新发现同类一行**——第 229 行 `config.cookie_status.includes('已配置')`（后端中文状态值比较）按同口径加 `i18n-allow`，已并入技术债 #32 范围。**G-010 复核**：警告文件数与批前同为 **3 个、无新增**；`ValidityConfig.vue` 有效行 387 → **390**、`WechatTrustIP.vue` 242 → **246**（二者**均未进入 400 警告区**，阶段 1 报告把「A 类行数 53/43」误记为「有效行/警告区」）；反而是 `SettingsTabValidity` 111 → 101、`SettingsTabCircuit` 92 → 82（4 个阶梯输入改 `v-for="i in 4"` 复用参数化 key）。受控测试：新增 `views/settings/SettingsTabsI18n.test.ts`（11 例，覆盖 11 个组件的 zh↔en 切换）+ `SettingsView`/`ValidityConfig`/`FileMonitor` 各补 1 例切换；前端 37 文件 / 256 测试全绿。 |
| v1.25 | 2026-09-27 | **批 1 通知域 i18n 化 → 存量 786 → 627**：`NotificationConfig.vue`（77 行）、`NotificationLogsView.vue`（72）、`NotificationBell.vue`（8）、`settings/SettingsTabNotification.vue`（2）共 **159 行 A 类文案**全部改走 `t()`，基线 **61 → 57 文件、786 → 627 行**。新增 `notification.*` 命名空间（`channel` / `settings` / `config` / `logs` / `bell`），三语各 +175 行，叶子键 129 → **307**（`check_i18n_key_count.py` 三语对齐 PASS）。两个设计决定：① **事件类型 → key 用命名约定派生**（`notification.config.event.<type>` / `notification.logs.event.<type>`，配 `te()` 存在性守卫、未知类型原样回显），而非 35/36 条字面量映射表——省 36 行样板，`NotificationLogsView.vue` 有效行 **400 → 390** 未被推入 G-010 警告区（若用字面量表会是 428）；② **不在批内统一事件文案**：同一次后端事件的显示名在两页措辞不同（6 处，如 `公告抓取完成` vs `公告抓取`、`定时扫描异常` vs `扫描异常`），本批按"保持既有可见文案"处理，两套 key 并存，是否统一留待决策。`NotificationConfig.vue` 有效行 **425 → 438**（G-010 警告区，未逼近 490 → 不触发当轮必拆）。复用既有 key：`common.cancel`、`common.save_failed`。 |
| v1.24 | 2026-09-27 | **删除 C-3 死代码 → 取消 `EXEMPT_DEAD_CODE`**（决策 1）：删 `web/src/types/dashboard.ts` 整文件（24 行中文）与 `web/src/constants/sourceMapping.ts` 的 `SOURCE_LABEL`（3 行中文，文件保留——`SOURCE_TO_URL` 被 `AnnounceView`/`LegacyRedirect` 使用）。删除前 `git grep` 全库确认零消费方（`WIDGET_LIBRARY`/`createDefaultWidgets`/`DashboardWidget`/`WidgetDefinition`/`DashboardLayoutV1`/`WidgetType`/`SOURCE_LABEL` 均只有定义行；无 `import()`/`require()`/barrel 再导出）。`EXEMPT_DEAD_CODE` 与 `exemption_reason()` 的对应分支一并删除，路径级豁免只剩语言包本体 `EXCLUDE_FILES`；同时删掉 B0 引入但**全仓库无调用方**的 `collect_files(keep_exempt=…)` 形参（其 docstring 声称供 `--report`/`--update-baseline` 使用，实际两处都未传）。受控测试仍 19 例（`test_path_exempt_files_are_skipped` 改为只遍历 `EXCLUDE_FILES`）。**基线不变**：786 行/61 文件——被删的两文件因豁免从不进基线；按含豁免文件计的真实存量 829 → **802**。 |
| v1.23 | 2026-09-27 | **G-040 注释口径修复 + 路径级豁免**：`strip_comments()` 由「只认行首 `//` + 非字符串感知的 `/*…*/` 正则」改为**字符串状态机**——修复两类错误：① **误报 48 行**（行尾 `//` 注释里的中文被当成文案，19 个文件，如 `config/themes.ts` 16 行、`useThemeSync.ts` 7 行）；② **漏报 3 行**（`accept="image/*"` 的 `/*` 与后面任意 `*/` 配对，把中间真实文案整段抹平，实测 `SettingsTabAppearanceMixed.vue:78/82/107`）。新增**路径级豁免** `EXCLUDE_FILES`（语言包本体 `lib/primevueLocale.ts`，16 行）与 `EXEMPT_DEAD_CODE`（零外部引用死代码 `types/dashboard.ts` 24 行 + `constants/sourceMapping.ts` 3 行，R-003 不擅自删）。受控测试 14 → **19 例**（新增：尾随注释不报 / 字符串内 `//` 仍报 / `/*` 不吞代码 / 路径豁免生效且不波及其它文件）。存量基线 **897 → 786**（−111）。 |
| v1.22 | 2026-09-26 | 新增 **G-040 i18n 硬编码检查**（`scripts/check_i18n_hardcoded.py`）：`web/src/**/*.{vue,ts}` 去掉注释后出现中日韩统一表意文字即记一处，只拦**超出基线**的新增（基线 `scripts/i18n_hardcoded_baseline.txt`，格式 `<路径>::<行数>`：新文件有中文全报、存量文件只报多出来的行、变少仅 `[STALE]` 提示）。豁免=注释 + 行内 `i18n-allow`（本行或上一行）。起因：`SettingsTabSchedule.vue` 整页 0 处 `t()`、文案全硬编码中文，而此前**无门禁**可拦——`check_i18n_key_count.py` 只比 locales 顶层 key，与组件是否用 i18n 无关。同批把该脚本升级到 **v1.1.0**：新增**叶子键路径**对齐（顶层一致 ≠ 三语一致；实测曾存在 9 个叶子漂移而该脚本仍 PASS），叶子不一致即阻断，空对象 `{}` 记为一个叶子；连带把 `tests/test_i18n_key_count.py` 中固化旧语义的 1 例改写为“深层键漂移必须报错”并补 3 例。已接入 `check_all.sh --fast`（G-039 之后）与 CI `test-frontend` 步骤；配套 14 例受控测试 `tests/test_check_i18n_hardcoded.py`。存量：**76 个文件 / 897 行**（最高 `NotificationConfig.vue` 77 行），仅建基线不要求一次清完。 |
| v1.21 | 2026-09-26 | 新增 **G-039 冲突标记检查**（`scripts/check_no_conflict_markers.py`）：禁止带 `<<<<<<<` / `=======` / `>>>>>>>` 的内容入库。起因是一次合并产生了带冲突标记的提交却通过了全部门禁（解析脚本断言失败后 `git add`/`git commit` 仍执行）。扫描范围=显式路径 > 暂存区 > 全库已跟踪文件；`=======` 只在成块时判违规（Markdown Setext 下划线不误伤）；白名单仅限测试本门禁自身的 fixture。已接入 `check_all.sh --fast`（G-012 之后）与 CI `repo-compliance`；配套 8 例受控测试 `tests/test_check_no_conflict_markers.py`。 |
| v1.20 | 2026-09-26 | 修正版本历史表的既有格式缺陷（技术债 #27）：v1.16 与 v1.15 两行原被写在同一个物理行上（**拼接处两个管道符相邻、缺的是换行符**，非缺行首 `|`；单行 879 字符）→ 在 `||` 之间补一个换行，拆为两个独立表行（471 + 408 = 879 字符）；内容一字未改，仅恢复渲染。 |
| v1.19 | 2026-09-26 | G-031 补第三条缺口映射（技术债 #24）：`pilotstd/download/` → `docs/reference/download-pipeline.md`（新建文档），映射总数 11 → **12**，无死映射。`pilotstd/download/` 此前不在表里，改下载适配器不触发任何文档同步——#21 的三处流程变化（hcno 权威来源＝openstd 搜索页、端点族 `/bzgk/std/*`、新增全文下载页 `showGb?type=download`）只写进了代码 docstring。**受控验证**（与 TD-13 同款手法）：仅暂存 `pilotstd/download/adapters/openstd_download.py` 末尾一行注释 → 脚本 **FAIL** 并输出 `[G-031] FAIL: pilotstd/download/ 已变更，但 docs/reference/download-pipeline.md 未同步更新`、`EXIT=1`；`git restore --staged` + 还原文件后 `git status` 干净、脚本回到 `PASS: 无变更文件` / `EXIT=0`。 |
| v1.18 | 2026-09-26 | 修复 `check_all.sh` 前端类型检查步骤的**两个**缺陷（#11 收尾时发现）：① 裸命令 `(cd web && npx vue-tsc --noEmit)` 在 `set -euo pipefail`（L6）下失败即中止整个门禁，紧随其后的 `log_fail` 分支**永远不可达** → 表现为"没有任何 FAIL 行、退出码 1"，把"工具缺失/类型错误"误报成"门禁挂了"（三条并行分支的提交者各自撞到同一现象）；改为把命令写进 `if` 条件。② 更严重：`web/tsconfig.json` 是**方案式配置**（`"files": []` + 仅 `references`），**不带 `-p` 时 vue-tsc 不检查任何文件、恒返回 0** → 这一步长期是**假绿**（注入真实 `TS2322` 后仍输出 PASS），而 CI 的 `test-frontend` 跑的是 `pnpm run type-check`＝`vue-tsc -p tsconfig.app.json --noEmit`；已改为与 CI 同口径。**验证**：正常 `EXIT=0`；注入类型错误 → `❌ [FAIL] vue-tsc 类型检查` 出现、脚本**继续跑完**后续门禁、`EXIT=1`；还原后 `EXIT=0`。全仓 `scripts/*.sh` 扫描 `$?` 仅此一处，无同类模式。 |
| v1.17 | 2026-09-26 | G-012 **注释检查**脚本按 G-010 拆解（技术债 #11）：`scripts/check_g_012_comment_density.py` 有效行 457 → **311**，其中近 200 行是纯数据（`TOOL_DIRECTIVES` 工具指令前缀、`LANG_WHITELIST` 中文注释白名单、`_LANG_WHITELIST_PATTERN`、`TERM_TRANSLATIONS` 术语对照表）→ 整体搬到 `scripts/_comment_lang_data.py`（159 有效行），脚本以 `from _comment_lang_data import ...` 复用，判定逻辑一行未动。**门禁行为零变化**：拆解前后用同一份显式文件清单（464 个 `.py`，`pilotstd/`+`docker/`+`scripts/`）分跑，输出各 80 行、逐行一致（含 `[LANG]` 警告项）。 |
| v1.16 | 2026-09-26 | G-012 检查脚本按 G-010 拆解（技术债 #11 紧急项）：`scripts/check_g_012_sql_schema.py` 有效行 497 → **139**，SQL 文本解析层（`SQL_KEYWORDS`/`PYTHON_BUILTINS`/`_SQL_FUNCTIONS` + 13 个纯函数）整体搬到 `scripts/_sql_schema_parser.py`（370 有效行），脚本以 `from _sql_schema_parser import ...` 复用；**门禁行为零变化**——拆解前后脚本自身输出逐行一致（各 36 行，diff 为空），仍 PASS（0 处不一致 / 73 条 SQL）。同批：`docker/auth.py` 490 → 394（拆出 `docker/_static_token.py`），G-010 警告区 10 → **8**，无文件 ≥490。本次一并确认 G-012 的 `--fast` 位置未变（见「执行入口」表） |
| v1.15 | 2026-09-25 | G-031 补齐两条长期缺口映射（技术债 #13/#14）：`pilotstd/core/` → `docs/architecture/modules/core.md`、`pilotstd/announcement/` → `docs/reference/announcement-pipeline.md`，映射总数 9 → **11**，无死映射（自检：源前缀与目标文档均存在）。验证方式为受控功能测试——仅暂存 `pilotstd/core/audit.py` 一处改动时 G-031 会 FAIL 并要求同步 core.md。修复过程中连带发现并修正 `core.md` 自身过时内容（schema 版本 v53→v59、文件数 50+→70、补 `config/service.py` 与 notification 子文件、门禁编号 G-032→G-031） |
| v1.14 | 2026-09-21 | G-027 纳入本地 `check_all.sh --fast`：该门禁原先只在 CI `test-frontend` 跑，本地 pre-commit 覆盖不到 —— 新增 Vue 组件漏写 `defineOptions` 时"本地全绿、CI 红"，且它会连带阻断 `version`/镜像构建 job，代价是多跑一整轮 CI 与一次镜像缺席（2026-09-21 实测事故：`FavoriteStatusTag.vue`）。同时补登 G-027 到门禁总览表 |
| v1.13 | 2026-09-21 | G-012 注释语言（[LANG] 警告，不阻断）清理并明确保留口径：67 项告警逐条手工改写为中文（**禁用 `--fix`** —— 其实现是"先替换术语、再删除所有英文字母"，会把注释改成病句）；**跨文件查找键保留英文并登记清单**，共 9 处：门禁编号 `G-038`、ADR 编号 `ADR-007`、提交哈希 `57f58a6c`（3 处）、文档路径 `docs/governance/gates.md` 与 `docs/adr/README.md`、表名 `app_preferences` 与 `user_favorites`（迁移索引需点名真实表）。判据：注释要"可读且信息完整"，能中文化的一律中文，用作查证入口的标识符不意译。仅注释改动已用 token 级比对证明（29 文件 token 流与 HEAD 完全一致） |
| v1.12 | 2026-09-21 | G-010 / G-012 改为**只评判入库产物**：新增 `scripts/_gate_paths.py`（`git ls-files --others --ignored --exclude-standard --directory` 计算忽略集合），两个门禁经 `is_git_ignored()` 跳过 `.gitignore` 声明的本地草稿。起因：全量扫描把 `logs/*.py` 一并判定，产生 G-012 22 项假阳性阻断 + G-010 2 项超长函数阻断，使与之无关的提交无法通过。判据与落地同时写入 `governance-principles.md` §3.4「只评判入库产物」 |
| v1.11 | 2026-09-13 | 按"事实归属"判据重定 G-031 映射并列出缺口：目标文档必须**承载该源路径的事实**，每个变更文件按最长匹配前缀归属唯一文档 —— 修正两处配对错（`pilotstd/announcement/parser.py` 曾指向只描述 `pilotstd/scan/parser/` 的 parser.md；`pilotstd/manager/facade/_scan.py` 曾指向只描述 `pilotstd/scan/` 的 scan.md 且与 manager 规则重复），改为 `pilotstd/scan/parser/` → parser.md、`pilotstd/scan/` → scan.md，`manager/facade/_scan.py` 归 manager.md；`docs/adr/` 目标改为真正的 ADR 索引 `docs/adr/README.md` 且仅新增/删除/重命名时联动；登记缺口 `pilotstd/core/`→core.md、`pilotstd/announcement/`→announcement-pipeline.md 未覆盖 |
| v1.10 | 2026-09-13 | 修复 G-031 四条**死映射**：源前缀 `pilotstd/core/parser.py`、`pilotstd/core/_scan.py`、`pilotstd/ui/main_window.py`、`docs/architecture/decisions/` 在仓库中均已不存在（模块已迁移，ADR 迁至 `docs/adr/`），导致这 4 条永不触发、门禁实际只守 5 条。脚本前缀对齐真实路径（`pilotstd/announcement/parser.py`、`pilotstd/manager/facade/_scan.py`、`pilotstd/ui/main_window/`、`docs/adr/`），9 条全部生效；同时修正"不存在时告警不阻断"的错误描述（`block` 模式下目标文档缺失同样是阻断） |
| v1.9 | 2026-09-13 | G-031 新增机器生成产物豁免：`docs/governance/capabilities_registry.md` 单独变更不再要求同步 README（重生成只改时间戳，AGENTS.md §七 又强制其随代码提交，否则每次重生成都被迫做装饰性改动或绕过门禁）；豁免命中打印 `[G-031] SKIP`，同批含人工文档变更时仍阻断 |
| v1.8 | 2026-09-13 | 确立检查放置原则"看输入在哪里可靠"：新增 `--local` 模式（本地专属），G-031 从 `--guards` 移出、**严格只挂本地**（本仓库以直推 main 为主，CI 中 `origin/base..HEAD` 恒空 → 假绿，属"放 CI 就是错的"）；`--guards` 明确为"入库产物"类（CI 权威 + 本地 fail-fast）；文档补"放置原则"判据表与三类划分 |
| v1.7 | 2026-09-13 | 按"检查跟随产物位置"定案两处放置：G-031 放**本地**（并入暂存区变更，提交前即生效；CI 侧保留 check_docs_sync.py 校验入库文档）；能力矩阵同步放 **CI**（新增 `scripts/check_capabilities_sync.py` 并接入 repo-compliance，重生成后忽略时间戳行比对入库内容）；「生成与守护的分工」表随之更新 |
| v1.6 | 2026-09-13 | 明确"生成在本地、守护分两处"的分工；G-032 纳入 `--guards`（本地守护本地产物，CI 复用同一实现守护入库文档）；`trinity-gate.yml` 改回 `--deep`（CI 不生成、不上传 artifact），清理空转步骤；登记 G-031 与 capabilities_registry 同步两处缺口 |
| v1.5 | 2026-09-13 | 修复 `check_all.sh` 参数解析（支持多模式叠加，未知参数报错退出）；新增 `--guards` 只读治理守护模式并接入 pre-commit 钩子（原 `--fast --docs` 的 docs 部分从未执行）；补充"执行入口"章节 |
| v1.4 | 2026-08-24 | G-010 升级 v2：>500 行阻断新增拆分验证（拆分证据 + 原文件 ≤500 行，缺一不可）；警告档（400-500 行）行为不变 |
| v1.3 | 2026-08-20 | 移除 G-016（与 G-011 重复）；补齐 G-015 脚本并接入 `check_all.sh --fast`；G-032 补充 CI 行为说明 |
| v1.2 | 2026-07-19 | 新增 G-037（触发条件对齐）、G-038（历史遗留错误清零） |
| v1.1 | 2026-07-18 | 新增 G-035（测试联动）、G-036（文档联动） |
| v1.0 | 2026-07-14 | 初始版本，收录 10 项门禁 |
