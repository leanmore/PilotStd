# 专项：长任务周期进度汇报（D-2）

> 状态：**已实现**（2026-10-18，v0.142.0）。
> 关联：通知阶段 2（`task_progress`）、`pilotstd/task/queue.py`、`docker/scheduler.py`。

## 需求（用户 2026-10-18 澄清）

不是"任务开始/结束时各发一条"，也不是桌面 60 秒长阶段节流，而是：

> 按**任务已运行时长**做**定时汇报**（例如每 5~10 分钟一条），把当前进度更新给用户。

## 设计草案

| 项 | 方案 |
|---|---|
| 周期 | 配置 `notification.progress_interval_minutes`，默认 5，允许 5~10，非法值回落 5 |
| 数据源 | 运行中任务：`task_queue` 的 `running` 记录（completed/total/started_at）；管道：`pipeline_runs` 的 `running` 记录（current_step/progress） |
| 触发 | 调度器每分钟扫描一次；对每个运行中实体，若 `now - last_report >= interval` 且进度有变化 → 发一条 `task_progress` |
| 去重 | 同一实体同一进度百分比只报一次；任务完成/失败发终态后清除计时 |
| 事件字段 | `task_id`、`task_name`、`completed`、`total`、`percent`、`elapsed_minutes`、`step` |
| 渠道 | 走既有 `send_event` 策略（Web/Webhook/桌面托盘由既有开关决定），不新增渠道 |
| 停止 | 任务进入终态或暂停时停止汇报；暂停不累计时长 |

## 已确认（用户 2026-10-18）

1. **覆盖范围**：只报管道任务（scan/query/download/archive），还是 `task_queue` 的所有任务？
2. **汇报渠道**：只 Web 站内 + 桌面托盘，还是也发 Webhook/企微（会显著增加消息量）？

确认后按上述设计实现：新增 `pilotstd/core/notification/progress_reporter.py` + `task_progress` 构建器 +
调度器接线 + 5~10 分钟窗口/去重测试。

## 不做的事

- 不改变现有"完成/失败"通知的语义与频率；
- 不复用桌面 60 秒长阶段窗口（面向 toast 防轰炸，语义不同）。

## 实现结果（2026-10-18）

- 后端：`progress_reporter.TaskProgressReporter` + `task_progress` 事件/构建器/三语 i18n；
- 接线：Docker 调度器每分钟 tick；管道 `update_step` 阶段切换即时回调；
- 渠道：默认四渠道统一 `send_event`，周期默认 5 分钟（夹紧 5~10）；
- 前端：任务中心每 30 秒自动刷新；
- 详细记录：[D-2 完成记录](../archive/2026-10-18-d2-task-progress-completion.md)。
