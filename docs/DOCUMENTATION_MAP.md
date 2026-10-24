# PilotStd 文档地图（DOCUMENTATION_MAP）

> **层**：治理（怎么做事）｜现状（系统现在什么样）｜指引（怎么做某类事）｜历史（为什么变成这样）｜期望（接下来做什么）
> **用法**：先读 `index.md`（入口，12 份必读），需要找某类文档时查本表；**排期**看 `ROADMAP.md`。
> **维护**：新增文档必须在本表加一行；文档归档时从本表移入 §三/§四，并注明去向。
> **更新**：2026-10-24（全量重建，117 篇）

## 一、统计

| 层 | 篇数 | 说明 |
|---|---|---|
| 治理 | 12 | 规则、门禁、索引 |
| 现状 | 27 | 架构与模块说明书、运维入口 |
| 指引 | 33 | 操作指南、规范、诊断案例 |
| 历史 | 32 | 决策、记录、债务、实现摘要 |
| 期望 | 13 | 路线图与在办计划 |
| **合计** | **117** | 不含历史归档区与本地归档区 |

## 二、全量目录

| 文档 | 层 | 内容 | 更新 |
|---|---|---|---|
| `docs/DOCUMENTATION_MAP.md` | 治理 | — | 2026-10-18 |
| `docs/governance/PROJECT_GOVERNANCE.md` | 治理 | PilotStd 项目治理总纲 | 2026-10-18 |
| `docs/governance/README.md` | 治理 | PilotStd 治理文档中心 | 2026-10-23 |
| `docs/governance/archive_migration_protocol.md` | 治理 | 归档迁移协议 | 2026-09-26 |
| `docs/governance/capabilities_registry.md` | 治理 | 能力登记簿（自动生成） | 2026-10-22 |
| `docs/governance/file-inclusion-criteria.md` | 治理 | 文件入仓判断标准 | 2026-07-16 |
| `docs/governance/gates.md` | 治理 | 门禁清单（Gates） | 2026-10-23 |
| `docs/governance/governance-principles.md` | 治理 | 治理体系原则 | 2026-09-27 |
| `docs/governance/notification_coverage.md` | 治理 | 通知系统覆盖度基线 | 2026-10-06 |
| `docs/governance/p3-review-checklist.md` | 治理 | P3 人工审查 Checklist | 2026-08-21 |
| `docs/governance/verification-antipatterns.md` | 治理 | 验证反模式集（本项目实测确认） | 2026-10-02 |
| `docs/index.md` | 治理 | PilotStd 文档索引 | 2026-10-18 |
| `docs/adapters/README.md` | 现状 | 适配器维护清单 | 2026-10-17 |
| `docs/analysis/http-requests-inventory.archived.md` | 现状 | HTTP 请求迁移清单 | 2026-08-21 |
| `docs/analysis/site_classification_partial.md` | 现状 | 标准查询站点分类分析结果 v1.1（2026-08-17） | 2026-08-17 |
| `docs/analysis/v1_vs_v2_routing_comparison.md` | 现状 | v1 vs v2 路由选择对比报告 | 2026-08-17 |
| `docs/architecture.md` | 现状 | — | 2026-10-22 |
| `docs/architecture/governance-summary.md` | 现状 | G-010 代码规模治理 — 完整汇总 | 2026-09-27 |
| `docs/architecture/modules/core.md` | 现状 | 模块文档：核心引擎（Core） | 2026-10-24 |
| `docs/architecture/modules/manager.md` | 现状 | 模块文档：管理模块（Manager） | 2026-10-24 |
| `docs/architecture/modules/parser.md` | 现状 | 模块文档：标准号解析器（Parser） | 2026-09-13 |
| `docs/architecture/modules/query.md` | 现状 | 模块文档：查询适配器（Query Adapters） | 2026-10-18 |
| `docs/architecture/modules/scan.md` | 现状 | 模块文档：扫描模块（Scan） | 2026-10-18 |
| `docs/architecture/modules/ui.md` | 现状 | 模块文档：UI 主窗口（MainWindow） | 2026-10-18 |
| `docs/architecture/overview.md` | 现状 | PilotStd 项目架构总览 | 2026-10-17 |
| `docs/architecture/refactoring-analysis.md` | 现状 | 大文件包化分析汇总 | 2026-09-27 |
| `docs/architecture/technical-debt-registry.archived.md` | 现状 | 技术债登记簿（已归档，停止维护） | 2026-09-27 |
| `docs/ci-lessons.md` | 现状 | CI 修复经验总结 | 2026-10-23 |
| `docs/configuration/README.md` | 现状 | 系统配置说明 | 2026-09-13 |
| `docs/deployment/README.md` | 现状 | 部署运维指南 | 2026-10-01 |
| `docs/design/site_classification_v1.md` | 现状 | 标准查询站点分类方案 v1.1 | 2026-08-17 |
| `docs/development.md` | 现状 | 创建虚拟环境 | 2026-10-21 |
| `docs/development/documentation-policy.md` | 现状 | 文档同步策略 | 2026-09-27 |
| `docs/development/g-010-enforcement.md` | 现状 | G-010 代码规模控制规则 | 2026-08-23 |
| `docs/flaky_e2e.md` | 现状 | 不稳定 E2E 用例追踪 | 2026-07-24 |
| `docs/migrations/README.md` | 现状 | 数据库迁移说明 | 2026-10-17 |
| `docs/notification_event_dictionary.md` | 现状 | PilotStd 通知事件字典 | 2026-09-21 |
| `docs/observability/README.md` | 现状 | 监控与可观测性 | 2026-10-17 |
| `docs/query/README.md` | 现状 | 查询引擎完整文档 | 2026-08-20 |
| `docs/guides/Docker使用指南.md` | 指引 | PilotStd Docker 使用指南 | 2026-10-22 |
| `docs/guides/cleanup-io-isolation-2.0.md` | 指引 | 文件系统 I/O 隔离 2.0：从扁平数据到树形结构的范式进化 | 2026-07-16 |
| `docs/guides/download-flow-engine-pattern.md` | 指引 | 可测性重构记录：核心业务流的纯逻辑提取与 I/O 隔离范式 | 2026-07-16 |
| `docs/guides/persistence-engine-pattern.md` | 指引 | 可测性重构记录：UI 持久化与状态管理的纯逻辑提取范式 | 2026-07-16 |
| `docs/guides/query-summary-engine-pattern.md` | 指引 | 可测性重构记录：数据分组与状态映射的纯逻辑提取范式 | 2026-07-16 |
| `docs/guides/refactoring-lessons.md` | 指引 | 大函数拆分经验记录 | 2026-09-26 |
| `docs/guides/settings-io-engine-pattern.md` | 指引 | 可测性重构记录：配置管理模块的纯逻辑提取范式 | 2026-10-01 |
| `docs/guides/人工测试方案.md` | 指引 | 人工测试方案 | 2026-09-26 |
| `docs/guides/用户帮助文档.md` | 指引 | PilotStd 用户帮助文档 | 2026-07-16 |
| `docs/reference/adapter-development.md` | 指引 | 适配器开发指南 | 2026-07-25 |
| `docs/reference/announcement-pipeline.md` | 指引 | 公告解析入库流程 | 2026-10-24 |
| `docs/reference/announcement-sources.md` | 指引 | 公告来源标识映射表 | 2026-10-22 |
| `docs/reference/coding-standards.md` | 指引 | 编码规范详细版 | 2026-08-24 |
| `docs/reference/download-pipeline.md` | 指引 | 下载流程（openstd 国家标准全文公开系统） | 2026-10-18 |
| `docs/reference/fixture-schema.md` | 指引 | 适配器 Fixture 统一 Schema | 2026-08-21 |
| `docs/reference/i18n-troubleshooting-sop.md` | 指引 | i18n 翻译缺失 — 排查与修复 SOP | 2026-07-29 |
| `docs/reference/notification-user-guide.md` | 指引 | 通知系统说明 | 2026-10-02 |
| `docs/reference/pre-commit-checklist.md` | 指引 | 提交前自检清单 | 2026-07-19 |
| `docs/reference/settings-ui-spec.md` | 指引 | Settings 页面 UI 组件开发规范 | 2026-08-05 |
| `docs/reference/ui-components.md` | 指引 | 前端 UI 组件规范 | 2026-10-23 |
| `docs/reference/版本管理规范.md` | 指引 | PilotStd 版本管理规范 | 2026-07-19 |
| `docs/reference/环境需求.md` | 指引 | PilotStd 环境需求 | 2026-08-23 |
| `docs/reference/附录一 标准代号完整清单.md` | 指引 | 附录一 标准代号完整清单 | 2026-07-19 |
| `docs/testing/coverage-report.md` | 指引 | 覆盖率报告 | 2026-10-17 |
| `docs/testing/e2e-guide.md` | 指引 | E2E 测试指南 | 2026-08-03 |
| `docs/testing/e2e-test-manifest.md` | 指引 | E2E 测试用例索引 | 2026-10-17 |
| `docs/testing/engine-mock-guide.md` | 指引 | Engine/DB Mock 基础设施使用指南 | 2026-08-04 |
| `docs/testing/integration-guide.md` | 指引 | 集成测试编写指南 | 2026-08-03 |
| `docs/testing/known-issues.md` | 指引 | 已知问题 | 2026-10-18 |
| `docs/testing/playbook.md` | 指引 | Testing Playbook | 2026-08-02 |
| `docs/testing/security-known-issues.md` | 指引 | Known Security Issues | 2026-10-17 |
| `docs/testing/testing-baseline.md` | 指引 | Testing Baseline (E2E + Integration) | 2026-09-26 |
| `docs/testing/下载适配器测试方案.md` | 指引 | 下载适配器测试方案 | 2026-09-26 |
| `docs/adr/ADR-001-modal-dialog-auto-clicker.md` | 历史 | ADR-001: ModalDialogAutoClicker — 事件驱动模态对话框自动处 | 2026-08-20 |
| `docs/adr/ADR-002-handler-governance.md` | 历史 | — | 2026-08-20 |
| `docs/adr/ADR-003-persistence-pattern.md` | 历史 | — | 2026-08-20 |
| `docs/adr/ADR-004-io-isolation.md` | 历史 | — | 2026-08-20 |
| `docs/adr/ADR-005-event-bus.md` | 历史 | — | 2026-08-20 |
| `docs/adr/ADR-006-ui-hold-strategy.md` | 历史 | — | 2026-08-20 |
| `docs/adr/ADR-007-favorite-archive-decouple.md` | 历史 | ADR-007: 收藏与归档下载解耦 | 2026-09-13 |
| `docs/adr/ADR-008-wait-worker-elimination.md` | 历史 | — | 2026-08-20 |
| `docs/adr/ADR-009-crontrigger-validity.md` | 历史 | ADR-009：CronTrigger 替代间隔式时效性调度 | 2026-08-20 |
| `docs/adr/ADR-010-mixin-refactor.md` | 历史 | ADR-010：Mixin 重构 16→1 | 2026-08-20 |
| `docs/adr/ADR-011-dashboard-singleton-floating-menu.md` | 历史 | ADR-011: 首页仪表盘状态集中化与悬浮工作台菜单（A2 迁移） | 2026-08-21 |
| `docs/adr/ADR-012-multi-user-architecture.md` | 历史 | ADR-012: 多用户基础架构改造（A3 迁移） | 2026-08-21 |
| `docs/adr/ADR-013-health-check-decoupling.md` | 历史 | ADR-013: 健康检查与业务任务解耦轮询机制 | 2026-09-25 |
| `docs/adr/ADR-014-routetag-request-cancellation.md` | 历史 | ADR-014: 前端 HTTP 请求取消 routeTag 三层机制 | 2026-08-21 |
| `docs/adr/ADR-015-route-engine-v2-funnel.md` | 历史 | ADR-015: 标准查询路由引擎 v2.0 — 三级漏斗路由 | 2026-08-21 |
| `docs/adr/ADR-016-standard-name-resolution.md` | 历史 | ADR-016: 标准名称解析——「最高可得阶段名」回退链与对外边界命名统一 | 2026-10-05 |
| `docs/adr/ADR-017-announcement-three-column.md` | 历史 | ADR-017：首页公告三栏分类 | 2026-10-17 |
| `docs/adr/README.md` | 历史 | — | 2026-10-18 |
| `docs/debt/01-archive-closed.md` | 历史 | 技术债 · 已完成归档（历史留痕） | 2026-10-17 |
| `docs/debt/02-accepted.md` | 历史 | 技术债 · 技术上无解 / 已接受（含不还的代价） | 2026-10-16 |
| `docs/debt/03-open.md` | 历史 | 技术债 · 可修复、尚未修复 | 2026-10-18 |
| `docs/debt/04-watch.md` | 历史 | — | 2026-10-18 |
| `docs/debt/05-audit-2026-10-17.md` | 历史 | 全项目体检（2026-10-17）：发现清单与处置批次 | 2026-10-18 |
| `docs/records/2026-10-18-announcement-gap-audit.md` | 历史 | 公告抓取缺口审计：2026-09 / 2026-10 | 2026-10-18 |
| `docs/records/2026-10-18-d13-coverage-plan.md` | 历史 | D-13 覆盖率补测计划（2026-10-18 基线后修订） | 2026-10-21 |
| `docs/records/2026-10-18-d2-task-progress-completion.md` | 历史 | D-2 完成记录：长任务周期进度汇报 | 2026-10-18 |
| `docs/records/2026-10-21-announcement-count-audit.md` | 历史 | 公告计数审计（2026-10-21，v0.147.0） | 2026-10-22 |
| `docs/records/2026-10-22-open-issues-project.md` | 历史 | 2026-10-22 遗留问题专项（reconcile / 通知 / 技术债） | 2026-10-23 |
| `docs/records/2026-10-24-doc-audit.md` | 历史 | PilotStd 文档与仓库整理审计（2026-10-24） | 2026-10-24 |
| `docs/records/d13-baseline-2026-10-18.md` | 历史 | D-13 覆盖率基线（2026-10-18） | 2026-10-18 |
| `docs/reference/implementation-digest.md` | 历史 | 实现摘要（Implementation Digest） | 2026-10-24 |
| `docs/technical-debt.md` | 历史 | — | 2026-10-18 |
| `docs/ROADMAP.md` | 期望 | PilotStd 路线图（ROADMAP） | 2026-10-24 |
| `docs/plans/README.md` | 期望 | 计划文档 | 2026-10-03 |
| `docs/plans/batch5-terminology-design.md` | 期望 | 第 5 批方案设计：术语表 + 禁用词门禁 | 2026-10-01 |
| `docs/plans/moviepilot-investigation/02-pilotstd-gap-analysis.md` | 期望 | PilotStd vs MoviePilot 差距分析报告 | 2026-10-03 |
| `docs/plans/notification-redesign/00-README.md` | 期望 | 通知架构重设计（索引 + 结论速览 + 裁决） | 2026-10-16 |
| `docs/plans/notification-redesign/02-目标架构.md` | 期望 | 02 目标架构设计 | 2026-10-05 |
| `docs/plans/notification-redesign/03-实施路径.md` | 期望 | 03 实施路径（六阶段） | 2026-10-06 |
| `docs/plans/notification-refactor-design.md` | 期望 | 事件通知模块重构设计（i18n / 模板 / 文案 / 覆盖度 / 聚合） | 2026-10-02 |
| `docs/plans/notification-system-design/00-framework.md` | 期望 | 通知系统方案框架 | 2026-10-03 |
| `docs/plans/notification-system-design/02-framework-update.md` | 期望 | 框架更新：裁决录入 + 分档通知策略初版 | 2026-10-03 |
| `docs/plans/notification-system-design/06-spec-and-phasing.md` | 期望 | SSOT 重建方案：五处澄清 + 两处补充澄清 + 重做方案 | 2026-10-05 |
| `docs/plans/notification-system-design/07-impl-design-A.md` | 期望 | 步 A 实施设计：渠道端到端收敛 | 2026-10-03 |
| `docs/plans/notification-system-design/08-统筹日程.md` | 期望 | 08 通知系统 · 统筹日程与待办清单（统筹法分析） | 2026-10-16 |

## 三、历史归档区（`docs/archive/`，67 篇）

2026-10 之前的过程稿，**冻结不动**（该路径在 CI 黑名单内，新增/改名会被拦）。需要追溯时按日期目录查找。

## 四、本地归档区（`docs/.local/archive/`，78 篇）

2026-10-24 移出的过程稿，**不在 git 内**（`docs/.local/` 已忽略）。其结论已沉淀到 `docs/reference/implementation-digest.md`；原件按原相对路径存放，需要细节时直接打开。

## 五、维护规则

| 场景 | 做法 |
|---|---|
| 新增文档 | 放到对应层的目录；在本表加一行；若属 AGENTS §8.1 触发项，同批加 `index.md` 与 AGENTS 表 |
| 文档过期 | 结论并入 `implementation-digest.md` 或对应说明书后，移到 `docs/.local/archive/<日期>/`，从本表删除 |
| 计划完成 | 提炼 ADR → 记入 `records/` → 从 `plans/` 移出；ROADMAP 勾选并在 §五 变更记录留痕 |
| 门禁相关 | 改 `docs/governance/` 同批改 `README.md`（G-031）；改 `scripts/` 同批改 `gates.md` |
