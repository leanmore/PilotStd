# PilotStd 治理文档中心

## 文档索引

| 文档 | 用途 | 状态 |
|------|------|------|
| [gates.md](gates.md) | 门禁清单（G-005~G-050）与版本历史；执行入口见 `scripts/check_all.sh`。**v2.16（2026-10-24）**：Q9 裁决换算——"声明 vs 实现"并入 G-045 的 B1 维度并留痕。**v2.17（2026-11-03）**：补「运维脚本（非门禁）」说明——`scripts/encrypt_config_secrets.py` 不参与任何门禁模式。**v2.18（2026-11-03）**：docs 同步检查修非 ASCII 路径转义（`core.quotepath=false`）。**v2.19（2026-11-05）**：新增审计工具 `scripts/audit_api_matrix.py`（非门禁）；**v2.20（2026-11-05）**：登记 G-051 API 权限矩阵门禁（`--check` 接入 CI）；**v2.21（2026-11-05）**：修复 G-051 CI 步骤误删 Upload coverage data 的 YAML 结构；**v2.22（2026-11-05）**：备份下载端点（FileResponse）加入 response_model 豁免清单；**v2.23（2026-11-05）**：登记 G-052 文档漂移门禁（路由/配置/表名与 docs 对齐）；**v2.24（2026-11-08）**：W1-U1 检查器/信号修正（property 白名单代理 / signal callback 形式 / error_occurred 接状态栏 / 删 query_result_ready 死信号）；**v2.25（2026-11-08）**：bandit 切 HIGH 阻断（`--severity-level high`，8 条 HIGH 清理至 0，MEDIUM 仍软）；**v2.26（2026-11-08）**：security-scan 升 Pillow 13/urllib3 2.8，pip-audit 对 ecdsa/python-jose 加带理由 ignore，OCR 冒烟通过；**v2.27（2026-11-08）**：G-013/030/031/033 变更范围不可知时 exit 2；**v2.28（2026-11-08）**：G-013 支持 --range 并接入 CI（repo-compliance）；**v2.29（2026-11-09）**：`except: continue` 不纳入第 4 类（裁定见 gates.md G-050 段）；**v2.30（2026-11-09）**：scripts 门禁读文件失败/可选依赖失败改为 `[WARN]` 留痕（返回值语义不变）；**v2.31（2026-11-09）**：git 失败 → exit 2、8 处 continue 跳过加 `[WARN]`、G-013 区分「文件不存在」与「git 不可用」；**v2.32（2026-11-09）**：G-050 纳入 scripts/ 扫描（基线 46/57/90，排除 scripts/archive/）；**v2.33（2026-11-09）**：docs-sync 规则 target 审计（8 条中 5 条指向死文档：4 条改指活文档 + 1 条删除，余 7 条）；**v2.34（2026-11-09）**：`check_all.sh --ci` 本地复刻 CI 文档联动口径（默认不启用）；**v2.35（2026-11-09）**：归档/索引 11 处 debug 升 warning，G-050 基线 debug 90 → 79；**v2.36（2026-11-09）**：公告/通知/watcher 6 处升 warning，基线重算 return 57→54 / debug 79→73；**v2.37（2026-11-09）**：查询/UI 5 处收口，G-050 终值 46/50/72（193→168），U-3/U-4 闭环 | 活跃 |
| [governance-principles.md](governance-principles.md) | 治理体系元原则（三件套、决策链、门禁设计） | v1.0 |
| [glossary.json](glossary.json) | 术语唯一数据源（G-044 门禁输入）：49 条术语的三语用词、`forbidden` 禁用词组、`aliases` 可接受写法，以及 `exempt_keys`（17）/ `exempt_terms`（10）两层白名单 | 活跃 |
| [notification_coverage.md](notification_coverage.md) | 通知系统覆盖度基线（**42** 事件 × i18n/e2e/审计/术语 四维度；**2026-10-05 阶段 4 · P6 · 4c** 起含平台层事件 `desktop_toast`，其 L-22 专项已闭环），新增事件的准入检查清单；由 `scripts/audit_notification_coverage.py`（G-045 门禁）扫描生成。**4d 增补**：**层级结构维度**由 `tests/test_notification_class_layer_contract.py`（4 例）守护——类别清单同序同集 / 事件→类别映射逐项相等 / 每类至少一个事件承接（`manual_test` 例外）/ `spec_hash` 对层结构敏感（`gates.md` v1.85） | 活跃 |
| [verification-antipatterns.md](verification-antipatterns.md) | 验证与报告方法论的反模式集（口径 / 可复现性 / 检测器判别力 / 抽象时机），每条附可复现的判别方式 | 活跃 |
| [ACCEPTANCE_CASES.md](ACCEPTANCE_CASES.md) | U36 治理验收用例（7 条：操作 + 一句话判据 + 代码/表/配置依赖）；含 W-001 缺失说明与当前证据强度 | U36 / 2026-11-09 |
| [ISSUE_LEDGER.md](ISSUE_LEDGER.md) | U36 全量治理问题台账（37 条：P0 2 / P1 8 / P2 13 / P3 14），每条含证据、来源、影响 AC、修复方案/代价/触发条件；2026-11-10 更新 P1-01/P1-02（手动计数 + 中间报告真实进度） | U36 / 2026-11-10 |
| [file-inclusion-criteria.md](file-inclusion-criteria.md) | 文件入仓五条规则（R1-R5） | v1.0 |
| [capabilities_registry.md](capabilities_registry.md) | 非功能性能力登记簿 | 活跃 |
| [../guides/refactoring-lessons.md](../guides/refactoring-lessons.md) | 拆分经验 + **拆分前检查项**（注释密度预估 / G-010 拆分证据；原 `refactoring_checklist.md` 已于 `efa7514a` 删除） | 活跃 |
| [archive_migration_protocol.md](archive_migration_protocol.md) | 归档文件强制迁移流程 | 活跃 |
| [../testing/known-issues.md](../testing/known-issues.md) | 已知问题追踪 | v1.0 |
| [../adr/ADR-001-modal-dialog-auto-clicker.md](../adr/ADR-001-modal-dialog-auto-clicker.md) | 模态对话框自动处理方案 | 已接受 |
| [../technical-debt.md](../technical-debt.md) | 技术债登记（**唯一数据源**；旧簿已归档） | 活跃 |
| [../../CONTRIBUTING.md](../../CONTRIBUTING.md) | 贡献指南 | 活跃 |

---

# 能力遗产治理框架

## 为什么有这个框架？

在软件开发中，**非功能性能力**（后台线程、定时心跳、观测日志、缓存等）在代码重构时容易被忽略，导致功能静默丢失。

本框架通过**能力登记 + 重构检查 + 归档协议 + 自动化门禁**四层机制，确保这些能力在代码演进中得到守护。

### 真实案例

2026-05-31，`stress_01_pipeline.py` 中实现了 `ProgressReporter`（每30秒输出查询进度）和 `heartbeat()`（心跳线程防卡死）。2026-06-10，v4.1 重构将文件归档为 `_archived.py`，这两个能力**静默丢失**。直到 2026-06-22 用户执行全量压测时才发现进度输出缺失——**12天的静默期**。

如果当时有此框架，归档前的"能力提取"步骤会自动发现这两个能力，阻止静默丢失。

## 核心文档

| 文档 | 用途 | 何时阅读 |
|------|------|---------|
| [capabilities_registry.md](capabilities_registry.md) | 所有模块非功能性能力的唯一登记簿 | 重构前必查 |
| [../guides/refactoring-lessons.md](../guides/refactoring-lessons.md) | 拆分前必查：新模块注释密度预估（G-012 ≥3%）、拆分证据与 500 行阻断档（G-010）；原 `refactoring_checklist.md` 已删除 | 重构全程对照 |
| [archive_migration_protocol.md](archive_migration_protocol.md) | 归档文件时的强制迁移流程 | 执行 `git mv` 归档前 |

## 工具脚本

| 工具 | 用途 | 何时运行 |
|------|------|---------|
| `bash scripts/extract_capabilities.sh <file>` | 提取单个文件的能力清单（AST 静态分析） | 重构前 / 归档前 |
| `python tests/test_observability.py --check-all` | 验证所有必需能力是否存活 | PR 提交前 / CI 自动运行 |
| `bash scripts/check_no_migrating.sh` | 检查登记簿是否有未解决的迁移项 | CI 自动运行（阻断合并） |
| `python scripts/find_docs.py "<关键词>"` | 按关键词检索文档，返回相关文档与命中标题 | 任务开始/排查前 |

## 核心工作流

```
重构前 → 查登记簿 + 运行 extract_capabilities.sh → 记录待迁移能力
重构中 → 逐项迁移或明确放弃（commit 中说明理由）
重构后 → 更新登记簿 + 运行 test_observability.py --check-all
PR提交 → 填写 PR 模板中的"能力迁移状态"表 → CI 自动检查
归档前 → 运行 extract_capabilities.sh 并确保迁移完成
```

## 红线（不可违反）

1. **禁止**在未运行 `extract_capabilities.sh` 的情况下执行 `git mv` 归档文件
2. **禁止**在 `capabilities_registry.md` 中存在 `migrating` 条目时合并 PR（CI 会阻断）
3. **禁止**在 `test_observability.py --check-all` 存在 FAIL 时合并 PR（CI 会阻断）

## 能力登记簿字段说明

| 字段 | 说明 | 可选值 |
|------|------|--------|
| 模块路径 | 能力所在的文件 | 相对于项目根目录 |
| 能力名称 | 简短描述 | — |
| 实现位置 | 文件:行号 或 类.方法 | — |
| 类型 | 能力分类 | 后台线程 / 观测日志 / 缓存 / 生命周期管理 / 其他 |
| 必需性 | 重要程度 | `required`（缺失 CI 阻断）/ `recommended` / `optional` |
| 登记日期 | 首次登记日期 | YYYY-MM-DD |
| 状态 | 当前状态 | `active` / `deprecated` |

## 常见问题

**Q: 我新增了一个后台线程，需要登记吗？**

A: 需要。在 `capabilities_registry.md` 中对应模块下新增一条记录，状态为 `active`，必需性根据重要性标记 `required` 或 `recommended`。

**Q: 我重构时发现某能力已不再需要，可以删除吗？**

A: 可以。但必须在 `capabilities_registry.md` 中将状态改为 `deprecated`，并在 commit message 中说明删除理由，而非静默删除。

**Q: 紧急修复也需要走这个流程吗？**

A: 紧急修复（Bug Fix）若涉及代码修改但未改变模块结构，只需运行 `test_observability.py --check-all` 确认无 FAIL 即可，无需完整走重构流程。若涉及文件归档或模块重构，则必须走完整流程。

**Q: 登记簿中的能力太多了，我能跳过吗？**

A: `--required-only` 参数仅检查 `required` 级别能力。CI 也仅对 `required` 级别 FAIL 进行阻断。`recommended` 和 `optional` 级别的 WARN 不会阻断合并。


> v2.14（2026-10-18）：Governance Docs Check 已从独立 workflow 合并为 CI `repo-compliance` 步骤，并改用显式范围（`GOVERNANCE_DOCS_RANGE`）；不再维护 `governance-check.yml`。


## 2026-10-23 Node 安全基线

- CI Node 固定 22.23.4；生产镜像无 Node 运行时。

## 2026-10-28 归档协议历史 hash 标注
- `archive_migration_protocol.md` 中两处旧提交 hash（`cdb6705`/`be50271`）已标「历史提交已不可考」；映射与背景见 `docs/debt/03-open.md` A-18。

## 2026-10-29 G-013 接受前端测试
- `is_test_file` 增加 `web/src/**/*.test.ts`：前端修复带 vitest 变更即可用 `fix` 类型，不再被迫改 `chore`（A-19/B5）；详见 `gates.md` G-013 行。

## 2026-10-29 渠道 schema 互证（A-3）
- CI `test-backend` 增加 `scripts/check_channel_schema_parity.py`：校验 spec 派生 schema 与各渠道 `get_config_schema()` 的键/required/secret，失败阻断。

## 2026-10-30 模板 hook 与 i18n 基线（A-31）
- hook 回归改为三处注册面（`__init__.py`/`registry.py`/`_INDUSTRY_FALLBACK`）；i18n 基线移除已无命中的模板 hook 条目。

## 2026-10-30 A-28 配置分层与迁移
- 新增 `pilotstd/core/config/scope.py` 与 `scripts/migrate_notification_scope.py`（dry-run 默认、备份、幂等）。

## 2026-10-30 A-28 失败路径
- 迁移脚本备份/写入失败不写标记；`--reset`/`--force`；未知键告警一次；渠道白名单键 `notification.channels.allowed`。

## 2026-10-31 A-28 阶段二 B
- /test-event 系统关/用户关分别拦截；迁移 --rollback 导出全部 notification% 偏好后删迁移键与标记。

## 2026-10-31 A-6 统计脚本
- scripts/notification_429_baseline.py 按渠道统计 total/failed/429；本地库仅参考。


> **2026-11-02**：新增 CI 门禁 check_response_model_coverage.py（B 组 API 契约），gates.md 已同步。


> **2026-11-02 修正**：response_model 覆盖检查改为 AST 静态扫描。

---

## 治理体系原则（并入自 PROJECT_GOVERNANCE）

1. **能力必须有门禁守护**：任何非功能性能力（后台线程、观测日志、缓存、通知等）必须在能力登记簿中登记，并有至少一道门禁守护。
2. **门禁必须守护能力**：任何门禁必须至少守护一项能力，否则该门禁无存在价值。
3. **能力放置以模块文档/架构总览为准**：能力应放在与模块职责一致的层次；原“四层架构”文档已归档，现行放置依据为 `docs/architecture/overview.md` 与各模块文档。
4. **三端共享**：通用能力必须在共享层实现，端侧只做交互适配。

## 治理操作流程（新增能力 / 新增门禁 / 重构迁移）

### 新增能力

```text
识别新能力 → 在能力登记簿中登记
              ↓
判断能力放置层次 → 参考 docs/architecture/overview.md 与模块文档
              ↓
设计守护门禁 → 新增或复用现有 G-0xx
              ↓
更新门禁索引 → docs/governance/gates.md 建立能力↔门禁关联
              ↓
代码实现 → 在正确的分层中实现
              ↓
验证 → 运行门禁确认守护生效
```

### 新增门禁

```text
识别需要守护的能力 → 查能力登记簿
              ↓
设计门禁脚本 → 放入 scripts/check_g_0xx_*.py
              ↓
注册门禁 → 接入 .husky/pre-commit（本地）或 ci.yml 的 repo-compliance 步骤（入库产物）
              ↓
更新门禁索引 → docs/governance/gates.md 记录门禁与能力的关联
              ↓
验证 → 确认门禁能正确检测违规
```

### 重构 / 迁移

```text
查询能力登记簿 → 确认涉及哪些能力
              ↓
查询 docs/governance/gates.md → 确认哪些门禁守护这些能力
              ↓
运行 scripts/extract_capabilities.sh → 提取当前能力快照
              ↓
执行重构 → 迁移代码到新位置
              ↓
运行门禁 → 确认所有守护能力未丢失
              ↓
更新能力登记簿 → 记录能力的新位置
```

> 来源：`docs/governance/PROJECT_GOVERNANCE.md` v1.0（2026-06-29），2026-11-08 并入；原文已归档至 `docs/.local/archive/2026-11-08/docs/governance/`。
> **2026-11-08**：`PROJECT_GOVERNANCE.md` 已归档至 `docs/.local/archive/2026-11-08/docs/governance/`，其原则与流程已并入本文件。
> **2026-11-08**：通知系统设计 9 份原文已归档至 `docs/.local/archive/2026-11-08/docs/plans/`，导航见 `docs/architecture/notification-system.md`；`gates.md` 中的引用已改指归档区。

