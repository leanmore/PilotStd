# ADR 目录索引

> PilotStd 架构决策记录
> 目录：`docs/adr/`

---

## ADR 列表

| 编号 | 文件 | 标题 | 日期 | 状态 |
|------|------|------|------|:--:|
| 001 | [ADR-001](ADR-001-modal-dialog-auto-clicker.md) | 模态对话框自动点击器 | 2026-07-14 | ✅ Accepted |
| 002 | [ADR-002](ADR-002-handler-governance.md) | Handler 层混合策略治理 | 2026-07-16 | ✅ Accepted |
| 003 | [ADR-003](ADR-003-persistence-pattern.md) | 纯逻辑提取范式（Engine-Handler 分离） | 2026-07-16 | ✅ Accepted |
| 004 | [ADR-004](ADR-004-io-isolation.md) | I/O 隔离模式（零 I/O + 显式时间注入） | 2026-07-16 | ✅ Accepted |
| 005 | [ADR-005](ADR-005-event-bus.md) | EventBus 事件总线重构 | 2026-07-16 | ✅ Accepted |
| 006 | [ADR-006](ADR-006-ui-hold-strategy.md) | 纯 UI 编排文件维持策略 | 2026-07-16 | ✅ Accepted |
| 007 | [ADR-007](ADR-007-favorite-archive-decouple.md) | 收藏与归档解耦 | 2026-Q1→Q3 | ✅ Accepted |
| 008 | [ADR-008](ADR-008-announcement-three-column.md) | 首页公告三栏分类 | 2026-Q2 | ✅ Accepted |
| 009 | [ADR-009](ADR-009-crontrigger-validity.md) | CronTrigger 替代间隔式时效性调度 | 2026-Q3 | ✅ Accepted |
| 010 | [ADR-010](ADR-010-mixin-refactor.md) | Mixin 重构 16→1 | 2026-08-04 | 🗄 Deprecated（Related to ADR-001，不同主题无取代关系） |
| 011 | [ADR-011](ADR-011-dashboard-singleton-floating-menu.md) | 首页仪表盘状态集中化与悬浮工作台菜单 | 2026-08-21（迁移归档） | ✅ Accepted |
| 012 | [ADR-012](ADR-012-multi-user-architecture.md) | 多用户基础架构改造 v3.0 | 2026-08-21（迁移归档） | ✅ Accepted |
| 013 | [ADR-013](ADR-013-health-check-decoupling.md) | 健康检查与业务任务解耦轮询机制 | 2026-08-21（A4 提炼） | ✅ Accepted |
| 014 | [ADR-014](ADR-014-routetag-request-cancellation.md) | 前端 HTTP 请求取消 routeTag 三层机制 | 2026-08-21（A4 提炼） | ✅ Accepted |
| 015 | [ADR-015](ADR-015-route-engine-v2-funnel.md) | 标准查询路由引擎 v2.0 三级漏斗 | 2026-08-21（A4 提炼） | ✅ Accepted（部分实施） |

> 注：ADR-011/012 由 Claude Code 迁移计划（A2/A3）归档转化；ADR-013/014/015 由历史会话转录（A4）提炼。新增 ADR 均遵循既有模板与编号连续。

## ADR-007 演进链

### 原方案（2026-Q1）：时间维度解耦
- 收藏不触发即时下载，由定时任务异步执行
- 所有状态存于 `user_favorites` 单表
- 问题：状态耦合（6/7 状态值描述归档），重试失败，扩展困难

### 修订（2026-Q3, v44）：表级彻底解耦
- 新建 `favorite_downloads` 表独立承载归档状态机 [src: `_migrate_v44.py`]
- `user_favorites` 回归纯粹收藏语义（pending/cancelled）
- 三个服务文件改造为操作 `favorite_downloads` [src: `favorite_download.py`, `archive_retry_service.py`, `date_reminder.py`]

### ADR-009：CronTrigger 时效性调度
- **原方案缺陷**：5分钟轮询 + next_run 手动计算，99% 唤醒无效；时区不一致
- **新方案**：`CronTrigger(day_of_week, hour, minute, timezone=timezone.utc)` [src: `docker/scheduler.py:286`]
- **关键**：`reschedule_validity_job()` 配置变更后即时生效，无需重启
## 关联文档

- [架构决策摘要](../architecture.md) — 历史决策 + 快速参考
- [治理体系技术规范](../governance/trinity-technical-spec-v2.md) — 三位一体总览（治理体系总览 [ARCHIVED](../governance-overview.md)）
- [技术债登记](../technical-debt.md) — 已清理 / 待处理 / 维持现状
