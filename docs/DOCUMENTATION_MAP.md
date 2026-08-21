# 🗺️ 项目文档地图 (DOCUMENTATION_MAP)

> **用途**：快速定位项目文档，了解每份文档的用途、状态与位置。Harness 接到任务时应先读本地图，再按索引定位目标文档。
> **更新规则**：新增/修改/删除文档时，同步更新本地图对应条目；地图自身变更须经 G-032 文档健康度守护。
> **Created**: 2026-08-19 · 基于 266 个文档全量审计（docs/inventory/）与 8 批精读（docs/process/）

> ⚠️ **治理声明**：本文档地图的生成与维护遵循 `docs/development/documentation-policy.md` 中定义的入仓标准与归档协议。若地图内容与该 Policy 冲突，以 Policy 为准（并提 Issue 修复地图）。

---

## 一、文档分层体系

| 层级 | 职责 | 代表文档 | 阅读场景 |
| :--- | :--- | :--- | :--- |
| L0-入口 | 项目概述、快速开始、执行铁律 | `README.md`、`AGENTS.md` | 首次接触项目 / 任何任务开始 |
| L1-总览 | 系统架构全景、技术栈、数据流 | `docs/architecture/overview.md`、`docs/query/README.md` | 理解系统全貌 |
| L2-决策 | 架构决策记录与理由 | `docs/architecture.md`、`docs/adr/*.md` | 理解"为什么这样设计" |
| L3-模块 | 各模块详细设计与范式 | `docs/architecture/modules/*.md`、`docs/guides/*-pattern.md` | 开发/修改特定模块 |

> 四层不合并、不精简，保持分层互补；若发现某层内容越界，下沉到对应 L3 文档。

## 二、治理体系（Governance）

| 层级 | 文档 | 职责定位 | 维护状态 |
| :--- | :--- | :--- | :--- |
| L0 执行手册 | `AGENTS.md` | 开发者/AI 执行规则（R-规则：铁律/SOP/门禁 + P-规则：协作纪律） | 🟢 活跃 |
| L1 流程总纲 | `docs/governance/PROJECT_GOVERNANCE.md` | 能力-门禁-架构三件套流程定义 + 治理角色 | 🟢 活跃（2026-08-19 修断链） |
| L2 技术规格 | `docs/governance/trinity-technical-spec-v2.md` | 15 章技术规范（核心原则/交付物/强制执行层/健康度/提交粒度） | 🟢 活跃 |
| L3 治理原则 | `docs/governance/governance-principles.md` | 元原则、门禁设计哲学、承诺追踪 | 🟢 活跃 |
| 门禁清单 | `docs/governance/gates.md` | 全量门禁索引（门禁纪律见 AGENTS.md P-105） | 🟢 活跃 |
| 支撑规范 | `docs/governance/development-flow.md`、`docs/governance/prompt-crafting-guide.md`、`docs/governance/rule-quickref.md`、`docs/development/documentation-policy.md` | 决策请求协议 / 提示词规范 / 规则速查 / 文档同步策略 | 🟢 活跃 |
| L4 历史快照 | `docs/governance-overview.md` | ⚠️ ARCHIVED 历史治理快照（2026-07-16，Engine 表已失效） | 🔴 归档 |

## 三、核心架构与决策（Architecture & ADRs）

### 架构文档

| 文档 | 说明 | 状态 |
| :--- | :--- | :--- |
| `docs/architecture.md` | 决策速查 + 关键模型（Handler 组合/公告双表/收藏归档/迁移校验） | ✅ 有效 |
| `docs/architecture/overview.md` | 系统架构总览（技术栈/模块关系/数据流/数据库表全景）；v2 路由已标注灰度 | ✅ 有效 |
| `docs/architecture/modules/manager.md` | Manager 门面层结构 | ✅ 有效 |
| `docs/architecture/modules/query.md` | 查询引擎与适配器（⚠️ 适配器清单过时，以 registry.py 为准） | ⚠️ 需更新 |
| `docs/architecture/modules/parser.md` / `scan.md` / `ui.md` | 解析器/扫描/UI 模块结构 | ✅ 有效 |
| `docs/query/README.md` | 查询引擎完整文档（含 v2 路由灰度说明） | ✅ 有效 |
| `docs/adapters/README.md` | 适配器维护清单（21 生产 + 1 Mock，共 22） | ✅ 有效 |

### ADR 速查（5 态标记：✅ Accepted / ♻️ Superseded / ⛔ Rejected / 🗄 Deprecated / 📝 Proposed）

| 编号 | 标题 | 状态 |
| :--- | :--- | :--- |
| ADR-001 | 模态对话框自动点击器（测试基础设施） | ✅ Accepted |
| ADR-002 | Handler 层混合策略治理 | ✅ Accepted |
| ADR-003 | 纯逻辑提取范式（Engine-Handler 分离） | ✅ Accepted |
| ADR-004 | I/O 隔离模式（零 I/O + 显式时间注入） | ✅ Accepted |
| ADR-005 | EventBus 事件总线重构 | ✅ Accepted |
| ADR-006 | 纯 UI 编排文件维持策略 | ✅ Accepted |
| ADR-007 | 收藏与归档解耦 | ✅ Accepted |
| ADR-008 | 首页公告三栏分类（2026-08-19 补建独立文件） | ✅ Accepted |
| ADR-009 | CronTrigger 替代间隔式时效性调度（2026-08-19 补建独立文件） | ✅ Accepted |
| ADR-010 | Mixin 重构 16→1（原 ADR-001-mixin 重编号；Handler 组合系列） | 🗄 Deprecated（Related to ADR-001，无取代关系） |

> 索引：`docs/adr/README.md`；演进链：ADR-007 收藏归档、ADR-009 CronTrigger 详情见 README 内联。

## 四、开发者指南与规范（Guides & Specs）

| 文档 | 说明 | 状态 |
| :--- | :--- | :--- |
| `docs/guides/*-pattern.md`（5 个） | Engine 重构范式（persistence/settings-io/download/cleanup/query-summary） | ✅ 有效（ADR-002~004 引用） |
| `docs/guides/refactoring-lessons.md` | 大函数拆分经验 | ✅ 有效 |
| `docs/guides/人工测试方案.md` / `用户帮助文档.md` | 人工测试 / 用户帮助 | ✅ 有效 |
| `docs/reference/*.md`（13 个） | 适配器开发/公告 pipeline/编码规范/i18n SOP/pre-commit 清单等（AGENTS.md 触发表引用） | ✅ 有效 |
| `docs/design/site_classification_v1.md` | 站点分类方案 v1.1（v2 路由基础） | ✅ 有效 |
| `docs/superpowers/specs/`（近期 08-14~08-19 系列） | 功能设计 spec-lite/design 记录 | ✅ 有效 |
| `docs/archive/specs/功能规格说明书.md` | ⚠️ ARCHIVED（版本止于 1.15/06-16；物理归档至 archive/specs/） | 🔴 归档 |
| `docs/archive/specs/模块与功能清单.md` | ⚠️ ARCHIVED（06-30；生成脚本 update_docs.py 仍引用，映射已更新至 archive 路径） | 🔴 归档 |

## 五、运维与部署（Ops & Deployment）

| 文档 | 说明 | 状态 |
| :--- | :--- | :--- |
| `docs/configuration/README.md` | config.json 完整 Schema 入口 | ✅ 有效 |
| `docs/deployment/README.md` | 部署运维指南（后端/前端/Docker） | ✅ 有效 |
| `docs/observability/README.md` | 监控与可观测性（9 Metrics/query_metrics 表/Grafana） | ✅ 有效 |
| `docs/migrations/README.md` | 数据库迁移说明（最新 v51） | ✅ 有效 |
| `docs/guides/Docker使用指南.md` | Docker 使用指南（与 deployment/README 有重叠，待统一） | ✅ 有效 |
| `docs/ci-lessons.md` | CI 修复经验（含 §六 离线网络硬阻断） | ✅ 有效 |
| `docs/technical-debt.md` + `docs/architecture/technical-debt-registry.md` | 技术债摘要 / 详细登记（摘要-详情分工） | ✅ 有效 |

## 六、分析报告与快照（Analysis & Snapshots）

> ⚠️ **使用前提标注**：以下文档多为特定时间点的分析或快照，使用时须注意其上下文限制，防止脱离语境误用。

| 文档 | 日期 | 前置条件 / 上下文限制 |
| :--- | :--- | :--- |
| `docs/analysis/gongbiaoku_search_audit.md` | 08-17 | 根因类型 B（数据源不支持国际标准）；site_capabilities.yaml 配置依据 |
| `docs/analysis/query_metrics_routing_mismatch_20260816.md` | 08-16 | **存档用途**：未来重启路由优化时作上下文，不代表已落地代码 |
| `docs/analysis/site_classification_partial.md` | 08-17 | 当前分类结果（v1.1，21/21） |
| `docs/analysis/v1_cleanup_readiness.md` | 08-17 | **前置条件**：v2 灰度 ≥1000 查询后方可重新评估 |
| `docs/analysis/v1_vs_v2_routing_comparison.md` | 08-17 | v2 灰度评估依据（10 真实 Query）；由 compare_v1_v2_routing.py 生成 |
| `docs/issues/router_v2_feedback.md` | 08-17 | 能力模型数据缺口记录（阶段四输入） |
| `docs/flaky_e2e.md` | — | 不稳定 E2E 追踪（运维记录，不阻塞 CI） |
| `docs/testing/project-coverage-survey-2026-07-31.md` | 07-31 | 覆盖率快照（已被 coverage-report.md 自动生成取代） |
| `docs/testing/trinity-system-health-survey-2026-07-31.md` | 07-31 | 体系健康度快照 |
| `docs/testing/handler-health-report-2026-08-02.md` | 08-02 | Handler 清理后健康度快照（基准记录） |
| `docs/superpowers/reports/ci-risk-investigation-2026-08-06.md` | 08-06 | CI 风险调查（门禁设计指导） |
| `docs/known-issues.md` | — | 安全审计轨迹（SEC-001 已解决） |
| `docs/tech_debt_linux_ci.md` | 08-01 | Linux CI 技术债专项输入 |
| `docs/analysis/site_classification_partial_v1.0.md` | 08-17 | ⚠️ ARCHIVED（被 v1.1 取代） |

## 七、历史归档区（Archive）

| 位置 | 说明 |
| :--- | :--- |
| `docs/archive/2026-07-16-audit-reports/` | 2026-06 审计报告（CI/前端/安全/许可证等，仅供追溯） |
| `docs/archive/2026-07-16-historical-plans/` | 2026-06~07 历史实施计划（design/plan 成对，多数已落地） |
| `docs/archive/.../old-archive/2026-06-30/` | G-010 治理前的结构分析/功能清单/门禁索引 v1.0（已被 refactoring-analysis.md 合并） |
| `docs/archive/项目进度日志.md` | **权威版项目进度日志**（gen_daily_log.py 自动生成） |
| 各文件原位 ARCHIVED 警告头 | specs×2 / vulture-scan / v1.0 分类 / ttzb plan+design / exact-match-spec / governance-overview（见上各节） |

> **归档约定**（documentation-policy.md）：归档文档不再维护；若需追溯历史决策，按日期/编号检索。新归档文件原则上不入仓（gitignore）。

---

## 附：本地图生成依据

- 审计基线：`docs/inventory/all_docs_list.md`（266 个 .md）+ `docs/inventory/doc_audit_report.md`（§1-§8）
- 精读过程：`docs/process/reading_notes_batch_1~7.md`（8 批）
- 决策记录：`docs/process/pending_questions.md`（Q1~Q6 系列，人工裁决）
- 物理变更：2026-08-19 阶段 C（ADR 重编号/补建/5 态标记、断链修复、归档、矛盾修正、交叉引用）
