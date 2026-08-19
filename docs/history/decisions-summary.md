# 历史决策摘要

> 提炼自 [docs/archive/2026-07-16-historical-plans/](../archive/2026-07-16-historical-plans/)
> 仅收录最终被采纳的核心决策，已否决的方案不在本摘要中。

---

## 架构演进决策

| 决策 | 日期 | 关联归档 | 当前状态 |
|------|------|---------|:--:|
| Handler 组合模式（Mixin→Handler） | 2026-06-15 | [workflow-enforcement-design](../archive/2026-07-16-historical-plans/2026-06-15-workflow-enforcement-design.md) | ✅ 已落地（28 Mixin→14 Handler） |
| 纯逻辑提取范式（Engine-Handler 分离） | 2026-07-16 | [ADR-003](../adr/ADR-003-persistence-pattern.md) | ✅ 已落地（3 Engine / 58 测试） |
| EventBus 事件总线 | 2026-07-16 | [ADR-005](../adr/ADR-005-event-bus.md) | ✅ 已落地（5 Handler 迁移） |
| 三位一体治理体系（测试+门禁+文档） | 2026-06-15 | [quality-checker-design](../archive/2026-07-16-historical-plans/2026-06-15-quality-checker-design.md) | ✅ 已落地（CI 并行 + Engine 100%） |

---

## 基础设施决策

| 决策 | 日期 | 关联归档 | 当前状态 |
|------|------|---------|:--:|
| 通知按用户隔离 | 2026-07-12 | [notification-per-user-design](../archive/2026-07-16-historical-plans/2026-07-12-notification-per-user-design.md) | ✅ 已落地 |
| Docker 自动更新 + 镜像构建 | 2026-06-25 | [docker-auto-update-design](../archive/2026-07-16-historical-plans/2026-06-25-docker-auto-update-design.md) | ✅ 已落地 |
| Web 四页架构（首页/查询/下载/设置） | 2026-06-25 | [web-four-pages-design](../archive/2026-07-16-historical-plans/2026-06-25-web-four-pages-design.md) | ✅ 已落地 |
| CI 构建隔离（Windows/Linux 双平台） | 2026-07-01 | [build-isolation-design](../archive/2026-07-16-historical-plans/2026-07-01-build-isolation-design.md) | ✅ 已落地 |
| 数据库迁移加固 | 2026-07-09 | [migration-hardening-design](../archive/2026-07-16-historical-plans/2026-07-09-migration-hardening-design.md) | ✅ 已落地 |

---

## 查询与适配器决策

| 决策 | 日期 | 关联归档 | 当前状态 |
|------|------|---------|:--:|
| 桶查询引擎（6 阶段流水线） | 2026-06-17 | [bucket-query-design](../archive/2026-07-16-historical-plans/2026-06-17-bucket-query-design.md) | ✅ 已落地 |
| ahbz 适配器修复（keyWord vs code 参数） | 2026-06-17 | [ahbz-adapter-fix-design](../archive/2026-07-16-historical-plans/2026-06-17-ahbz-adapter-fix-design.md) | ✅ 已落地 |
| MoviePilot 持久化分析 | 2026-07-13 | [moviepilot-persistence-analysis](../archive/2026-07-16-historical-plans/2026-07-13-moviepilot-persistence-analysis.md) | ✅ 已落地 |

---

## 测试与质量决策

| 决策 | 日期 | 关联归档 | 当前状态 |
|------|------|---------|:--:|
| 全量压力测试方案 | 2026-06-16 | [全量压力测试设计](../archive/2026-07-16-historical-plans/2026-06-16-全量压力测试设计.md) | ✅ 已落地 |
| 自动管线链式修复（scan→query→download→archive） | 2026-06-13 | [auto-pipeline-chain-fix](../archive/2026-07-16-historical-plans/2026-06-13-auto-pipeline-chain-fix.md) | ✅ 已落地 |

---

## 关联文档

- [ADR 目录](../adr/README.md) — 8 个正式架构决策记录
- [治理体系技术规范](../governance/trinity-technical-spec-v2.md) — 三位一体总览（历史快照：[治理体系总览 ARCHIVED](../governance-overview.md)）
- [技术债登记](../technical-debt.md) — 当前技术债状态
