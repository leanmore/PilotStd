<!-- 本文件为临时迁移说明，将于 2026-10-16 删除 -->

# 文档迁移说明

> 迁移日期：2026-07-16
> 迁移原因：文档体系 v2.0 重构 Phase 1 — 安全隔离（物理移动，零内容变更）
> 可回滚：所有操作均通过 `git mv` 等价操作执行，`git checkout HEAD~1` 一键回滚

---

## 迁移对照表

### superpowers/ → archive/2026-07-16-historical-plans/

| 原路径 | 新路径 |
|--------|--------|
| `docs/superpowers/specs/*` (13 文件) | `docs/archive/2026-07-16-historical-plans/` |
| `docs/superpowers/plans/*` (14 文件) | `docs/archive/2026-07-16-historical-plans/` |
| `docs/superpowers/prompts/architecture_migration_review.md` | `docs/archive/2026-07-16-historical-plans/` |

### superpowers/reports/ → archive/2026-07-16-audit-reports/

| 原路径 | 新路径 |
|--------|--------|
| `docs/superpowers/reports/2026-07-03-win-startup-issues-investigation.md` | `docs/archive/2026-07-16-audit-reports/` |

### archive/2026-06-30/ → old-archive/

| 原路径 | 新路径 |
|--------|--------|
| `docs/archive/2026-06-30/` (20 文件) | `docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/` |

### 审计报告隔离

| 原路径 | 新路径 |
|--------|--------|
| `docs/security_audit.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/cicd_inventory.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/app_websocket_audit.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/frontend_polling_report.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/frontend_5features_status.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/存量资产审计与去重行动计划书.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/validity_checker_current_state.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/notification_trigger_candidates.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/ci_test_failure_investigation.md` | `docs/archive/2026-07-16-audit-reports/` |
| `docs/licenses.md` | `docs/archive/2026-07-16-audit-reports/` |

### 事件追踪隔离

| 原路径 | 新路径 |
|--------|--------|
| `docs/announcement_check_event_status.md` | `docs/archive/2026-07-16-event-tracking/` |
| `docs/announcement_event_status.md` | `docs/archive/2026-07-16-event-tracking/` |
| `docs/auto_scan_event_status.md` | `docs/archive/2026-07-16-event-tracking/` |
| `docs/b3_b4_trigger_locations.md` | `docs/archive/2026-07-16-event-tracking/` |
| `docs/backup_event_status.md` | `docs/archive/2026-07-16-event-tracking/` |
| `docs/batch_download_event_status.md` | `docs/archive/2026-07-16-event-tracking/` |

### 根目录杂项

| 原路径 | 新路径 |
|--------|--------|
| `项目进度日志.md` | `docs/archive/2026-07-16-historical-plans/` |

---

## Phase 2: 内容重构（2026-07-16）

### 2.1 删除事件追踪文件（6 个）

以下 6 份一次性功能缺口调查报告已删除（均为 2026-06-28 生成，内容已过期）：

| 原路径 |
|--------|
| `docs/archive/2026-07-16-event-tracking/announcement_check_event_status.md` |
| `docs/archive/2026-07-16-event-tracking/announcement_event_status.md` |
| `docs/archive/2026-07-16-event-tracking/auto_scan_event_status.md` |
| `docs/archive/2026-07-16-event-tracking/b3_b4_trigger_locations.md` |
| `docs/archive/2026-07-16-event-tracking/backup_event_status.md` |
| `docs/archive/2026-07-16-event-tracking/batch_download_event_status.md` |

空目录 `docs/archive/2026-07-16-event-tracking/` 已一并删除。

### 2.2 架构模块文档链接建立

- `docs/architecture.md` — 新增「模块结构详解」章节，指向 5 个模块文档
- `docs/governance-overview.md` — 新增「模块架构文档」章节，补充 5 个模块文档引用

### 2.3 历史决策摘要创建

- 新建 `docs/history/decisions-summary.md` — 提炼 15 项已采纳决策，附归档链接
- `docs/index.md` — 更新历史文档导航

### 2.4 防腐蚀元数据注入（7 个文件）

| 文件 | 注入元数据 |
|------|-----------|
| `docs/guides/Docker使用指南.md` | `Last-Reviewed=2026-07-16 / Review-Cycle=90d` |
| `docs/guides/refactoring-lessons.md` | 同上 |
| `docs/guides/人工测试方案.md` | 同上 |
| `docs/guides/用户帮助文档.md` | 同上 |
| `docs/reference/版本管理规范.md` | 同上 |
| `docs/reference/环境需求.md` | 同上 |
| `docs/reference/附录一 标准代号完整清单.md` | 同上 |

排除的范式文档（核心治理层，不受此约束）：`*-pattern.md`（4 个）+ `cleanup-io-isolation-2.0.md`（1 个）

---

## Phase 3: 机制落地（2026-07-16）

### 3.1 CLAUDE.md 规则追加

在 `### 3.5 文档联动义务` 之后新增两条强制规则：

- **3.6 支撑层文档防腐烂规则**：修改 `docs/guides/` 或 `docs/reference/` 下文档时，必须同步更新 `Last-Reviewed` 元数据
- **3.7 计划文档生命周期规则**：新计划存入 `docs/plans/`，实施完毕后提炼 ADR 并归档至 `docs/archive/`

同时修正了 3.5 中指向已删除目录 `docs/superpowers/` 的过期引用。

### 3.2 docs/plans/ 目录创建

- 新建 `docs/plans/README.md` — 明确 Active-only 原则 + 生命周期流程图
- `docs/index.md` 架构与治理区新增指向 `plans/README.md` 的导航链接

---

## 统计

| 类别 | 文件数 |
|------|:--:|
| 历史计划/设计 | 28 |
| 旧归档 (2026-06-30) | 20 |
| 审计报告 | 11 |
| 事件追踪 | 6 |
| 进度日志 | 1 |
| **合计** | **66** |

---

## 清理的目录

- `docs/superpowers/`（含 specs/ plans/ prompts/ reports/）
- `docs/archive/2026-06-30/`（移至 old-archive）
