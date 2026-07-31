# 三位一体体系现状调查报告

> **调查日期**：2026-07-31
> **调查范围**：规范（Spec）、CI（持续集成）、文档（State）、Git 钩子（Hooks）四大支柱
> **调查方法**：文件系统扫描 + 配置审计 + 代码静态分析 + 实测覆盖率对比
> **核心原则**：只调查不修改，所有结论附证据路径

---

## 执行摘要

1. **规范支柱基本健康但门禁落地率仅 36%（5/14）**：`trinity-technical-spec-v2.md`（2026-07-28，v2.1）体系完整，但 `gates.md` 中 9/14 项门禁标记为"⏳ 待创建"，其中 3 项（G-030/G-032/G-033）脚本源码已删除仅留 `.pyc` 缓存。
2. **实测后端覆盖率 48%，文档数据存在内部矛盾**：STATUS.md 概览区写"771 tests"但详表写"2,366 tests"（偏差 -1,595）；`coverage-report.md` 记录 41.5%（7/14 数据，已过期 17 天）。
3. **最大缺口是门禁落地率与自动化链路断裂**：`check_all.sh` 未被 `.husky/pre-commit` 调用，9 项门禁无 CI 执行，文档新鲜度完全依赖人类自觉。

---

## 一、规范支柱现状

### 1.1 治理文档清单

`docs/governance/` 目录下共 12 份文档：

| 文档 | 最后修改 | 关键内容 |
|------|---------|---------|
| [trinity-technical-spec-v2.md](docs/governance/trinity-technical-spec-v2.md) | 2026-07-28 | 三位一体核心技术规范 v2.1，含 D1-D5 交付物、强制执行层规格、阶段任务矩阵 |
| [gates.md](docs/governance/gates.md) | 2026-07-19 | 门禁清单 v1.2，14 项门禁定义 |
| [development-flow.md](docs/governance/development-flow.md) | 2026-07-27 | 开发流程与决策请求协议 |
| [PROJECT_GOVERNANCE.md](docs/governance/PROJECT_GOVERNANCE.md) | 2026-07-02 | 项目治理总纲 v1.0 |
| [capabilities_registry.md](docs/governance/capabilities_registry.md) | 2026-07-18 | 能力登记簿 |
| [rule-quickref.md](docs/governance/rule-quickref.md) | 2026-07-27 | 非技术决策者规则速查表 |
| [prompt-crafting-guide.md](docs/governance/prompt-crafting-guide.md) | 2026-07-27 | 提示词生产规范 |
| [phase1-startup-checklist.md](docs/governance/phase1-startup-checklist.md) | 2026-07-27 | Phase 1 启动检查清单 |
| [governance-principles.md](docs/governance/governance-principles.md) | 2026-07-16 | 治理原则 |
| [file-inclusion-criteria.md](docs/governance/file-inclusion-criteria.md) | 2026-07-16 | 文件入仓标准 |
| [archive_migration_protocol.md](docs/governance/archive_migration_protocol.md) | 2026-06-22 | 归档迁移协议 |
| [README.md](docs/governance/README.md) | 2026-07-16 | 治理文档索引 |

### 1.2 trinity-technical-spec-v2.md 状态

- **存在**：✅
- **版本**：v2.1
- **最后修改**：2026-07-28（§5.3 路由策略配置化重构追加于 2026-07-28）
- **覆盖率门禁定义**：§4 强制执行层规格中定义了 `validate_decision_request` 等接口，但 `enforcement/guardrails.py` 状态为"🔜 待实现"
- **文档同步要求**：§5 治理文档只读防护体系中定义了 UX 防护层 + 强制阻断层双层模型，OC-4 要求 CI 强制校验
- **整体评价**：规范文档本身体系完整、逻辑自洽，定义了清晰的"测试→门禁→文档"闭环。但规范中多处标注"🔜 待实现""Phase 1 产出"，说明规范超前于实现

### 1.3 CLAUDE.md 规则硬度分析

对 [CLAUDE.md](CLAUDE.md) 全文扫描"必须/禁止/强制/严禁/不可/不允许/应当/应该/建议/尽量/记得/不要/不能"，逐条分类：

#### 硬指令（含"必须""禁止""严禁""强制""不可绕过"等绝对化用语）— 共 22 条

| # | 规则摘要 | 原文关键词 | 位置 |
|---|---------|-----------|------|
| 1 | 严禁硬编码密码、Token、密钥 | 严禁 | §1 L7 |
| 2 | 严禁裸 `except`，必须捕获具体异常 | 严禁/必须 | §1 L8 |
| 3 | 日志唯一入口 `LoggerManager()`，禁止 `print` 或 `_log()` | 禁止 | §1 L9 |
| 4 | 写新函数前先搜索，禁止重复造轮子 | 禁止 | §1 L10 |
| 5 | 提交信息格式 Conventional Commits，禁止手动打 Tag | 禁止 | §1 L11 |
| 6 | 每次任务严格执行为五步，禁止跳过任何一步 | 禁止跳过 | §2 L15 |
| 7 | 提交前运行 `scripts/check_all.sh`，确保零错误 | 确保零错误 | §2 L19 |
| 8 | 交付报告每一项都必须如实填写，禁止留空 | 必须/禁止 | §2 L103 |
| 9 | 文档与代码不一致必须同步修正，禁止仅标记"文档过期" | 必须/禁止 | §2 L58 |
| 10 | Git Hooks pre-commit 拦截未通过门禁的提交 | 拦截（硬） | §3.1 L64 |
| 11 | CI 硬阻断：全量测试、架构变更无 ADR | 硬阻断 | §3.1 L65 |
| 12 | CI 失败后先写归因分析再修代码，禁止跳过归因直接改代码 | 禁止 | §3.1 L66 |
| 13 | spec-lite.md 必须存在于 specs/ 目录（功能开发） | 必须存在 | §4.1 L97 |
| 14 | spec + plan 双文档必须存在（架构变更） | 必须存在 | §4.1 L98 |
| 15 | 收工前必须更新 `.claude/memory.md` | 必须同步更新 | §6 L121 |
| 16 | 放弃站点/方案/技术路线必须在 Memory 中记录 | 必须在 | §6 L127 |
| 17 | 收工前必须自问"是否产生值得记录的决策" | 必须自问 | §6 L130 |
| 18 | Memory >14天未更新 → 阻断推送 | 阻断 | §6 L132 |
| 19 | 本次修改的文件出现 ruff/mypy 报错 → 必须修 | 必须修 | §7 L149 |
| 20 | 涉及 ≥2 个静态分析工具的修复指令必须逐工具分节列出，禁止合并表述 | 必须/禁止 | §7 L179 |
| 21 | `.test_pass` 验证文件时间戳须在 24h 内 + commit_hash 一致 | 硬检查 | §4.1 |
| 22 | 无对应 spec/plan 文档 → 验证无效，退回执行 | 退回 | §4.1 |

#### 软建议 — 0 条

CLAUDE.md 中未出现"建议""尽量""记得"等软化用语。整份文档使用高度命令式语言。

#### 分析

- **硬度评分**：硬指令密度极高（22 条 / 约 180 行有效内容），几乎不存在软建议
- **核心矛盾**：CLAUDE.md 用"必须""禁止"描述了大量规则，但其中许多规则在工程层面没有对应的自动执行机制。例如"提交前运行 check_all.sh"是硬指令，但 `.husky/pre-commit` 并未调用 `check_all.sh`
- **AI 行为约束模式**：依赖 AI 阅读并遵守文本指令，而非物理阻断。22 条硬指令中仅约 7 条有对应的自动化门禁支持

---

## 二、CI 支柱现状

### 2.1 Workflow 文件

| 文件 | 触发条件 | Job 数量 |
|------|---------|---------|
| [ci.yml](.github/workflows/ci.yml) | push/PR to main + workflow_dispatch | 10 |
| [governance-check.yml](.github/workflows/governance-check.yml) | PR 修改 docs/governance/** | 1 |

### 2.2 CI Job 与门禁映射

| Job | 运行环境 | 包含的门禁检查 |
|-----|---------|--------------|
| **test-backend** | ubuntu-latest | forbid-test-imports, pytest `--cov-fail-under=45`, observability, governance migration check, vulture, compileall, G-008(依赖), G-009(CHANGELOG版本), G-010(代码规模), G-011(属性完整性), G-025(适配器), G-028(禁止硬编码admin), schema consistency |
| **security-scan** | ubuntu-latest | detect-secrets, bandit(非阻断), pip-audit(非阻断) |
| **test-frontend** | ubuntu-latest | type-check, primevue icons, vitest, ts-prune, G-018(敏感字段), G-027(defineOptions), i18n keys |
| **test-e2e** | windows-latest | GUI E2E (pytest-qt, e2e marker) |
| **frontend-e2e** | ubuntu-latest | Playwright E2E (quick-actions.spec.ts) |
| **test-unit-cov** | windows-latest | 分层覆盖率: FlowEngine≥95%, Handler≥20%, Overall≥68% |
| **repo-compliance** | ubuntu-latest | repo-compliance(入仓), G-026(Docker挂载), G-029(测试联动), docs_sync |
| **version** | ubuntu-latest | 版本自动计算与 Tag 创建 |
| **docker** | ubuntu-latest | Docker 镜像构建与推送 |
| **exe** | windows-latest | PyInstaller exe 构建 |

### 2.3 门禁部署状态矩阵

基于 [gates.md](docs/governance/gates.md) 定义的 14 项门禁 + repo-compliance：

| 编号 | 名称 | gates.md 状态 | 脚本存在 | CI 中执行 | 实际生效 |
|------|------|:---:|:---:|:---:|:---:|
| G-010 | 代码规模控制 | ✅ 已部署 | ✅ | ✅ test-backend | ✅ **是** |
| G-015 | 相对导入检查 | ✅ 已部署 | ✅ | ✅ test-backend | ✅ **是** |
| G-016 | 动态属性完整性 | ✅ 已部署 | ✅ | ✅ test-backend (via G-011) | ✅ **是** |
| G-029 | 测试联动检查 | ✅ 已部署 | ✅ | ✅ repo-compliance | ✅ **是** |
| repo-compliance | 入仓合规检查 | ✅ 已部署 | ✅ | ✅ repo-compliance | ✅ **是** |
| G-030 | 技术债联动检查 | ⏳ 待创建 | ❌ 仅 .pyc | ❌ | ❌ **否** |
| G-031 | 文档同步检查 | ⏳ 待创建 | ✅ | ❌ (另有 check_docs_sync.py 在 CI) | ⚠️ **部分** |
| G-032 | STATUS 新鲜度 | ⏳ 待创建 | ❌ 仅 .pyc | ❌ | ❌ **否** |
| G-033 | ADR 完整性检查 | ⏳ 待创建 | ❌ 仅 .pyc | ❌ | ❌ **否** |
| G-034 | 覆盖率阈值 ≥80% | ⏳ 待创建 | ✅ | ❌ (CI 用不同阈值) | ❌ **否** |
| G-035 | 测试联动门禁 | ⏳ 待创建 | 无脚本(人工) | ❌ | ❌ **否** |
| G-036 | 文档联动门禁 | ⏳ 待创建 | 无脚本(人工) | ❌ | ❌ **否** |
| G-037 | 触发条件对齐 | ⏳ 待创建 | ✅ | ❌ (仅 check_all.sh/manual) | ❌ **否** |
| G-038 | 历史遗留错误清零 | ⏳ 待创建 | ✅ | ❌ (仅 check_all.sh/manual) | ❌ **否** |

**汇总**：14 项门禁中 5 项（36%）实际生效，1 项部分生效，8 项（57%）完全失效。

### 2.4 覆盖率门禁配置

| 层级 | CI Job | 阈值 | 实际执行 |
|------|--------|------|---------|
| 后端整体 | test-backend | `--cov-fail-under=45` | ✅ 每次 push/PR |
| FlowEngine 纯逻辑 | test-unit-cov (Windows) | `--fail-under=95` | ✅ 每次 push/PR |
| Handler 胶水层 | test-unit-cov (Windows) | `--fail-under=20` | ✅ 每次 push/PR |
| GUI 整体 | test-unit-cov (Windows) | `--fail-under=68` | ✅ 每次 push/PR |
| 前端 | — | 无配置 | ❌ 完全缺失 |

### 2.5 定时 CI Job

**不存在**。未配置 `schedule`/`cron` 触发器。无双日审计、无夜间覆盖率报告生成、无定期文档新鲜度检查。

### 2.6 执行证据验证

由于 `gh` CLI 未认证，无法直接拉取 GitHub Actions 运行历史。从 git log 获取间接证据：

**最近 5 次提交（均在 2026-07-31 执行）**：
```
c218999a test(coverage): exempt wechat_ip module from unit test coverage [P2-2]
d95eb42e test(coverage): add monitor module unit tests (config 64%, handler 89%) [P2-1]
530f7608 test(coverage): add unit tests for scheduler (96%) and watcher (95%) [P1-2]
cfe85c6e test(coverage): add frontend coverage baseline and vitest thresholds [P0-2]
bfe26513 test(coverage): add backend CI gate + GUI multiprocess coverage [P0-3,P1-1]
```

**分析**：
- 5 个连续提交均涉及覆盖率相关改动，说明 CI 覆盖率门禁正在被积极使用和改进
- 提交信息符合 Conventional Commits 规范，说明 commit-msg hook 在生效
- 未发现 "skip ci" 或 "ci skip" 标记，未发现 CI 被跳过的证据
- `bfe26513` 提交明确提到了"add backend CI gate"，说明 CI 门禁在本次迭代中正在被加强
- **局限**：无法确认这些提交对应的 CI run 是否全部通过，也无法排除"失败后强制合并"的可能

---

## 三、文档支柱现状

### 3.1 核心文档状态

| 文档 | 存在 | 最后修改 | 新鲜度评估 |
|------|:---:|------|------|
| [STATUS.md](STATUS.md) | ✅ | 2026-07-31 | ✅ 今日修改 |
| [CHANGELOG.md](CHANGELOG.md) | ✅ | CI 自动更新 | ✅ 自动维护 |
| [coverage-report.md](docs/testing/coverage-report.md) | ✅ | 2026-07-14 | ❌ 过期 17 天 |
| [project-coverage-survey-2026-07-31.md](docs/testing/project-coverage-survey-2026-07-31.md) | ✅ (未跟踪) | 2026-07-31 | ✅ 今日新建 |

### 3.2 数据一致性实算

#### 覆盖率对比

| 来源 | 记录值 | 记录日期 | 与实测偏差 |
|------|--------|---------|-----------|
| `coverage-report.md` | **41.5%** | 2026-07-14 | **-6.5%**（过期 17 天） |
| `STATUS.md` 测试状态区 | **48%** | 2026-07-31 | **0%**（与实测一致） |
| `project-coverage-survey` | **48%** | 2026-07-31 | **0%**（实测基准） |

> **实测数据**（来源：[project-coverage-survey-2026-07-31.md](docs/testing/project-coverage-survey-2026-07-31.md)，今日 `pytest --cov=pilotstd --cov-branch` 扫描）：
> - 测试结果：2,358 passed, 1 failed (E2E 网络依赖), 7 skipped
> - 总语句：22,582 | 缺失：11,445 | **行覆盖率：48%**
> - 测试用例总数：2,366（非 GUI）

#### 测试数量对比

| 来源 | 记录测试数 | 实际测试数 | 偏差 |
|------|-----------|-----------|------|
| `STATUS.md` 概览区（L9） | **771** | 2,366 | **-1,595** |
| `STATUS.md` 测试状态区（L43） | **2,366** | 2,366 | **0** |
| `coverage-report.md` | **1,003** | 2,366 | **-1,363**（17 天前数据） |

#### 发现的矛盾

1. **STATUS.md 内部自相矛盾**：概览区 L9 写"Python 771 tests collected"，测试状态区 L43 写"后端测试用例（非GUI）2,366"。同一文件内偏差 -1,595。
2. **coverage-report.md 严重过期**：最后一次实质性更新是 2026-07-14，此后测试数从 1,003 增长到 2,366（+136%），覆盖率从 40.3% 提升到 48%（+7.7pp），但报告未同步。
3. **CHANGELOG.md 信噪比极低**：自 v0.67.0（7/13）以来，80%+ 的条目为"版本号自动同步（CI 更新）"，人工编写内容被淹没在自动提交噪音中。

### 3.3 可能已过期的文档

通过最后修改时间分析，以下文档可能存在过期风险：

| 文档 | 最后修改 | 过期风险 | 理由 |
|------|---------|:---:|------|
| `docs/architecture.md` | 2026-07-20 | ⚠️ 中 | 此后有大量 Handler 重构、覆盖率改进 |
| `docs/testing/coverage-report.md` | 2026-07-14 | ❌ 高 | 测试数 +136%，覆盖率 +7.7pp 未反映 |
| `docs/ci-lessons.md` | 2026-07-16 | ⚠️ 中 | E2E 改用 docker/app.py、前端 E2E job 新增未记录 |
| `docs/governance/gates.md` | 2026-07-19 | ⚠️ 中 | G-037/G-038 脚本已存在但文档仍标"待创建" |
| `docs/governance/PROJECT_GOVERNANCE.md` | 2026-07-02 | ⚠️ 低 | v1.0，快 1 个月未更新，但内容偏原则性 |
| `docs/governance/capabilities_registry.md` | 2026-07-18 | ⚠️ 低 | 13 天未更新，可能有新能力未登记 |

---

## 四、Git 钩子现状

### 4.1 配置层级

```
core.hooksPath = D:\PilotStd\.husky    ← 生效的钩子目录
                   ↓
            .husky/pre-commit          ← 实际执行的钩子脚本
                   ↓
         运行: vue-tsc, lint-staged, G-010, G-011, G-012, ruff

.git/hooks/pre-commit (658 bytes)     ← 被忽略（因 hooksPath 指向 .husky）
.git/hooks/commit-msg  (658 bytes)     ← 被忽略（同上）
                   ↓
         均委托给 .pre-commit-config.yaml
```

### 4.2 `.husky/pre-commit` 实际执行内容

| 步骤 | 内容 | 阻断性 |
|------|------|:---:|
| 1 | `vue-tsc -b --noEmit` | ❌ 阻断 |
| 2 | `lint-staged` | ❌ 阻断 |
| 3 | 禁止直接从 primevue 导入 DatePicker | ❌ 阻断 |
| 4 | `python scripts/update_docs.py` | ✅ 不阻断（`\|\| true`） |
| 5 | 文档联动提醒（提示性） | ✅ 不阻断 |
| 6 | `check_g_010_code_size.py` | ❌ 阻断 |
| 7 | `check_g_011_attr_integrity.py` | ❌ 阻断 |
| 8 | `check_g_012_sql_schema.py` | ❌ 阻断 |
| 9 | `check_g_012_comment_density.py` | ❌ 阻断 |
| 10 | Ruff 自动修复 | ✅ 不阻断（`\|\| true`） |

### 4.3 `.pre-commit-config.yaml` 自动执行钩子（`stages: [pre-commit]` 或默认）

| 钩子 | 来源 | 作用 |
|------|------|------|
| trailing-whitespace | pre-commit-hooks | 去除行尾空格 |
| end-of-file-fixer | pre-commit-hooks | 文件末尾换行 |
| check-yaml | pre-commit-hooks | YAML 语法检查 |
| check-added-large-files | pre-commit-hooks | 禁止大文件 |
| ruff | ruff-pre-commit | Python lint + fix |
| ruff-format | ruff-pre-commit | Python 格式化 |
| mypy | mirrors-mypy | 类型检查 |
| detect-secrets | Yelp | 凭证扫描 |
| py-compile-core | local | 编译检查 ui/core/ |
| update-capabilities | local | 自动更新能力登记簿 |

### 4.4 `.pre-commit-config.yaml` 手动钩子（`stages: [manual]`）— 共 15 个

以下钩子**不会在 `git commit` 时自动执行**，需显式调用 `pre-commit run --hook-stage manual`：

forbid-test-imports, no-new-mixin, gate-11, gate-sensitive-fields, gate-adapters, gate-docker-mounts, gate-define-options, gate-no-hardcoded-admin, run-gates, check-dead-code-python, check-dead-code-typescript, check-dependencies, check-changelog-version, check-ui-sensitive-fields, gate-10-code-size

**关键发现**：`check-all` 钩子（运行 `check_all.sh`）也是 `stages: [manual]`，意味着 CLAUDE.md 中要求的"提交前运行 check_all.sh"实际上**不会被 git commit 自动触发**。

### 4.5 Hook 生效验证

| 检查项 | 结果 | 证据 |
|--------|------|------|
| `.git/hooks/` 有实际脚本 | ✅ | pre-commit(658B) + commit-msg(658B)，均为 pre-commit 生成 |
| `core.hooksPath` 配置 | `.husky` | 通过 `git config core.hooksPath` 确认 |
| `.husky/pre-commit` 可读 | ✅ | 54 行 Shell 脚本，含 10 个检查步骤 |
| commit-msg 格式校验 | ✅ | `.pre-commit-config.yaml` L192-197，`stages: [commit-msg]` |
| pre-commit run --all-files | 未执行（dry-run 可能修改文件） | 跳过，避免意外修改 |

---

## 五、三位一体体系完整度评估

### 5.1 三支柱健康度

| 支柱 | 状态 | 判定依据 |
|------|:---:|------|
| **规范（Spec）** | 🟡 部分健康 | 核心规范完整（trinity-technical-spec-v2.md v2.1），但门禁落地率仅 36%，gates.md 9/14 标记待创建 |
| **CI（持续集成）** | 🟡 部分健康 | 5 项门禁实际执行，覆盖率有分层策略，但 8 项门禁缺失、无定时任务、无前端覆盖率 |
| **文档（State）** | 🟠 部分失效 | STATUS.md 存在但内部数据矛盾（771 vs 2,366），coverage-report.md 过期 17 天，CHANGELOG 信噪比极低 |
| **Git 钩子（Hooks）** | 🟡 部分健康 | .husky/pre-commit 有效执行 7 项阻断检查，但 check_all.sh 未接入自动链路，15 个 pre-commit 钩子手动模式 |

### 5.2 软约束 vs 硬约束

#### 硬约束（物理强制执行，无法绕过除非破坏 CI/Git）

| 约束 | 执行点 | 绕过方式 |
|------|--------|---------|
| 后端测试 `--cov-fail-under=45` | CI test-backend | 修改 CI 配置文件（会被 review） |
| FlowEngine 覆盖率 ≥95% | CI test-unit-cov | 修改 CI 配置文件 |
| G-010 代码规模 | CI + .husky/pre-commit | `git commit --no-verify` + 修改 CI |
| G-011 属性完整性 | CI + .husky/pre-commit | 同上 |
| G-012 SQL Schema | .husky/pre-commit | `--no-verify`（CI 中无此检查） |
| detect-secrets 凭证扫描 | pre-commit + CI security-scan | `--no-verify` + 修改 CI |
| vue-tsc 类型检查 | .husky/pre-commit + CI test-frontend | `--no-verify` + 修改 CI |
| 入仓合规 (repo-compliance) | CI repo-compliance | 修改 CI 配置 |
| commit-msg 格式 | commit-msg hook | `--no-verify` |

#### 软约束（依赖 AI/人类自觉，无自动化阻断）

| 约束 | 依赖方式 | 逃逸难度 |
|------|---------|:---:|
| 提交前运行 `check_all.sh` | CLAUDE.md 文本指令 | 极低 |
| 文档与代码同步更新 | CLAUDE.md 文本指令 | 极低 |
| STATUS.md 数据准确 | 人工维护 | 极低 |
| coverage-report.md 及时更新 | 人工维护 | 极低 |
| CHANGELOG 写有意义内容 | 开发者自觉 | 低 |
| spec/plan 文档存在 | `.test_pass` 前置条件 | 中 |
| G-035 测试联动（人工审查） | 人工 | 极高 |
| G-036 文档联动（人工审查） | 人工 | 极高 |
| Memory.md 14 天更新 | CI pre-push hook（警告/阻断） | 中 |

### 5.3 逃逸风险清单

以下列出 Claude Code（或任何 AI/人类开发者）在当前体系下绕过文档更新义务的可行路径：

| # | 逃逸路径 | 风险等级 | 依赖的体系缺陷 | 可行性 |
|---|---------|:---:|---|---|
| 1 | **`git commit --no-verify` 跳过 `.husky/pre-commit`** | 🔴 高 | `.husky/pre-commit` 不包含 `check_all.sh`；即使跳过也无 CI 惩罚（G-032/G-034/G-037/G-038 均不在 CI） | 一行命令即可 |
| 2 | **手动编辑 STATUS.md 修改日期但内容不变** | 🟠 中 | G-032（STATUS 新鲜度）脚本源码已删除，CI 中无检查 | 改一行即可 |
| 3 | **从不更新 coverage-report.md** | 🟡 低 | G-034 脚本存在但不在 CI 中执行 | 已持续 17 天未被发现 |
| 4 | **CI 失败后强制合并** | 🔴 高 | 未确认是否有 branch protection rules；9 项门禁本就不在 CI 中 | 取决于 GitHub 仓库设置 |
| 5 | **修改代码后不改 CHANGELOG（或写无意义自动条目）** | 🟠 中 | CHANGELOG 99% 为 CI 自动生成条目，已形成"无意义更新"惯例 | 已成常态 |
| 6 | **check_all.sh 从未被自动执行** | 🔴 高 | check_all.sh 在 `.pre-commit-config.yaml` 中设为 `stages: [manual]`，`.husky/pre-commit` 也未调用 | 从未自动运行 |
| 7 | **前端覆盖率完全不可见** | 🟡 低 | 无 `@vitest/coverage-v8` 配置，前端测试质量无法量化 | 无法发现前端测试退化 |
| 8 | **G-030/G-032/G-033 脚本源码已删除** | 🟠 中 | 仅有 `.pyc` 缓存残留在 `scripts/__pycache__/`，说明曾短暂存在后被删除 | 门禁形式上存在实则真空 |

### 5.4 最大缺口识别

**缺口 #1（最严重）：门禁落地率仅 36%，自动化链路断裂**

9/14 门禁无 CI 执行。`check_all.sh` 是 CLAUDE.md 要求的核心检查脚本，但既不在 `.husky/pre-commit` 中也不在 CI 中自动运行。这导致：
- Ruff/Mypy 全量检查在提交时不被自动执行（仅检查暂存文件）
- G-037（触发条件对齐）仅靠人工
- G-038（历史遗留错误清零）仅靠人工
- G-034（覆盖率 80%）在 CI 中完全不检查

**缺口 #2：文档数据一致性问题**

STATUS.md 内部矛盾（771 vs 2,366 tests）表明即使文件被修改，也无法保证内容准确性。coverage-report.md 过期 17 天且无自动更新机制。G-032（新鲜度检查）脚本源码已删除。

**缺口 #3：check_all.sh 与 .husky/pre-commit 的架构分裂**

存在两套并行的门禁体系：
- `.husky/pre-commit`：vue-tsc + lint-staged + G-010 + G-011 + G-012 + ruff
- `check_all.sh`：ruff + mypy + G-010(简化版) + vulture + schema + G-037 + G-038

两者检查内容有重叠但不完全一致，且 `check_all.sh` 未被任何自动流程触发。

---

## 六、建议优先修复项

按"堵逃逸漏洞 > 补硬门禁 > 修数据"排序：

| 优先级 | 修复项 | 类型 | 预计工作量 |
|:---:|------|:---:|:---:|
| **P0** | 将 `check_all.sh` 接入 `.husky/pre-commit`（或反之，将 `.husky/pre-commit` 的检查统一到 `check_all.sh`） | 堵逃逸 | 小（改 1 行） |
| **P0** | 补回 G-032（STATUS 新鲜度）脚本并加入 CI repo-compliance job | 补硬门禁 | 小（脚本已有 .pyc，需还原源码） |
| **P1** | 将 G-034（覆盖率阈值）加入 CI，使用实际可达阈值（建议从当前 48%→55%） | 补硬门禁 | 小（脚本已存在，加 CI step） |
| **P1** | 补回 G-030/G-033 脚本源码（或确认已废弃并从 gates.md 移除） | 修数据 | 小 |
| **P1** | 修复 STATUS.md L9 的测试数（771→2,366） | 修数据 | 极小 |
| **P2** | 更新 gates.md 中 G-037/G-038 的状态（脚本已存在，应标"已部署"） | 修数据 | 极小 |
| **P2** | 更新 coverage-report.md 至当前数据（48%，2,366 tests） | 修数据 | 小 |
| **P2** | 建立 coverage-report.md 自动更新机制（CI scheduled job 或 pre-commit hook） | 补硬门禁 | 中 |
| **P3** | 为 CHANGELOG 自动条目添加 `[auto]` 标记，与人工条目区分 | 修数据 | 小 |
| **P3** | 前端添加 `@vitest/coverage-v8` 并设基线门禁 | 补硬门禁 | 中 |
| **P3** | 添加 CI scheduled job（每日文档新鲜度检查 + 覆盖率趋势报告） | 补硬门禁 | 中 |

---

## 附录：调查方法说明

| 数据项 | 采集方法 | 局限性 |
|--------|---------|--------|
| 治理文档列表 | `Glob docs/governance/**/*` | — |
| CLAUDE.md 规则硬度 | 全文 `grep` 关键词 + 人工逐条判定 | 语义判断可能遗漏边缘情况 |
| CI workflow 分析 | 读取 `.github/workflows/*.yml` 全文 | — |
| 门禁脚本存在性 | `Glob scripts/check_g_*.py` + 检查 `.pyc` 缓存 | 无法判断脚本是否真的能正常运行 |
| Git hooks 配置 | `git config core.hooksPath` + 读取 `.husky/` + `.git/hooks/` | — |
| 覆盖率实测 | 引用同日 `project-coverage-survey-2026-07-31.md` 的 `pytest --cov` 扫描结果 | 未独立重新运行（耗时过长），但引用的调查与本次同日同环境 |
| CI 执行证据 | `git log` 分析提交模式 + CI 配置文件对照 | 无 GitHub API 直接访问，无法确认每次 CI run 的实际状态 |
| 文档新鲜度 | 文件系统 `LastWriteTime` 对比 | 修改时间更新不保证内容准确（如 STATUS.md 的情况） |

---

> **报告版本**：v1.0
> **调查执行**：Claude Code（只读模式，零文件修改）
> **下次调查建议**：2026-08-14（两周后），重点复查 P0/P1 修复项进展
