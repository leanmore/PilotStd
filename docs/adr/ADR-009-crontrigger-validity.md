# ADR-009：CronTrigger 替代间隔式时效性调度

- **日期**：2026-Q3
- **状态**：✅ Accepted

## 上下文（Context）

时效性检查的定时调度早期采用 **5 分钟轮询 + next_run 手动计算**：

- 每次唤醒后手动计算下一次运行时间，99% 的唤醒无效（未到执行时刻）
- 时区处理不一致，跨时区部署时执行时刻偏差

## 决策（Decision）

改用 APScheduler **CronTrigger** 精确调度：

```python
CronTrigger(day_of_week, hour, minute, timezone=timezone.utc)
```

- 调度配置来源：`validity.first_weekday` / `validity.execute_time`（依据：pilotstd/core/config/defaults.py:95-96）
- 注册位置：docker/scheduler.py `_VALIDITY_JOB_ID` + `_get_validity_cron_kwargs()`（依据：docker/scheduler.py:303-309）
- **关键**：`reschedule_validity_job()` 在配置变更后即时生效，无需重启服务

## 后果（Consequences）

**正面**：
- 精确到分钟的执行时刻，无空唤醒
- 时区显式指定（UTC），跨时区部署行为一致
- 配置变更即时生效（reschedule 机制）

**负面**：
- 依赖 APScheduler 3.x 的 CronTrigger（已验证可用）
- 需维护 `_get_validity_cron_kwargs()` 将业务配置（周几/时刻）转换为 Cron 字段

> 本文档由 2026-08-19 文档整理从 ADR 索引内联描述补建（原详情仅内联在 ADR README）。
