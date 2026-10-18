# D-2 完成记录：长任务周期进度汇报

> 完成日期：2026-10-18
> 版本：v0.142.1（以最新 tag 为准）
> 状态：**已实现并合入 main**
> 关联：`docs/plans/task-progress-reporting.md`、`pilotstd/core/notification/progress_reporter.py`

## 一、需求（用户澄清后的最终口径）

- **范围**：所有任务（`task_queue` 全量 running 记录）+ 管道运行（`pipeline_runs` 的 running 记录）。
- **节奏**：按任务已运行时长做**定时汇报**，默认每 5 分钟一条（可配 5~10 分钟）；
  管道**阶段切换立即报**，其余按周期兜底。
- **渠道**：公共模块统一走 `send_event`，由既有通知策略分发到全部渠道
  （wechat / dingtalk / feishu / telegram），不按渠道写分支。
- **不刷屏**：同任务同周期只报一次；暂停/结束/失败后停止；短任务通常只在完成时通知。

## 二、实现清单

| 文件 | 改动 |
|---|---|
| `pilotstd/core/notification/progress_reporter.py` | 新增 `TaskProgressReporter`：周期扫描、阶段即时回调、去重、终态清理；周期夹紧 5~10 分钟 |
| `pilotstd/core/notification/event_spec_data.py` | 新增 `task_progress` 事件规格（payload 七字段、默认四渠道、`aggregation=aggregate`） |
| `pilotstd/core/notification/events.py` | `ALL_EVENTS` 登记 `task_progress`（事件总数 43） |
| `pilotstd/core/notification/_builders_task_results.py` | 新增 `_build_task_progress_message`（标题+正文+task_id/target_id） |
| `pilotstd/i18n/{zh_CN,en,zh_TW}.json` | 新增 `notification.task_progress.*` 三语键 |
| `pilotstd/core/topic_index_data.json` | `topic_by_event` 登记 `task_progress → done` |
| `pilotstd/task/pipeline_store.py` | 新增 `list_running()`；新增 `on_step_changed` 回调，`update_step` 步骤变化时即时触发 |
| `docker/app.py` | 组装汇报器、注册 `task_progress_report`、注入管道阶段回调；周期配置容错 |
| `docker/scheduler.py` | 每 60 秒 tick 一次（任务周期由汇报器内部节流） |
| `web/src/components/TaskManager.vue` | 任务/管道进度页打开期间每 30 秒自动刷新 |
| `tests/test_task_progress_reporter.py` | 7 例：周期、去重、终态清理、阶段即时、回调、夹紧、构建器 |

## 三、运行行为

| 场景 | 行为 |
|---|---|
| 普通任务运行 < 5 分钟 | 不报进度，完成时只发终态通知 |
| 长查询/长任务 ≥ 5 分钟 | 每 5~6 分钟一条 `task_progress`（含已完成/总数/百分比/已运行分钟） |
| 管道阶段切换 | `update_step` 触发回调，**立即**发一条（不等 tick） |
| 管道同阶段长时间运行 | 每 5~10 分钟兜底一条 |
| 任务结束/取消/失败 | 从 running 列表消失，计时状态清理，不再报 |
| 前端任务管理页 | 打开期间每 30 秒自动刷新任务/管道进度条 |

**配置**：`notification.progress_interval_minutes`，默认 5；非法/越界自动夹紧到 5~10。
**订阅**：默认四渠道；老配置由 `ConfigManager.populate_defaults` 自动补缺失键；
若某渠道收不到，检查该用户通知策略里是否订阅了 `task_progress` 类别。

## 四、验证证据

| 检查 | 结果 |
|---|---|
| `python -m pytest tests/test_task_progress_reporter.py -q` | **7 passed** |
| 通知契约相关（event_spec / e2e / mapping / topic / API / class layer） | **274 passed**（D-2 合入时） |
| `bash scripts/check_all.sh --fast --guards --local` | EXIT=0 |
| CI run 1099（阶段即时回调 + UTC 修正 + 完成记录） | 全部作业 success |
| 版本 | CI bump 至 **v0.142.1**（含阶段即时回调与 UTC 耗时修正） |

## 五、边界与已知限制

1. **桌面端本地进程未接周期推送**：本次接线在 Docker 调度器（`docker/app.py` + `docker/scheduler.py`）；
   桌面端的本地扫描/查询只在任务中心展示进度，不发周期通知。若需要桌面端同能力，可复用
   `TaskProgressReporter` 在 UI 侧加 QTimer（独立小改动）。
2. 任务 `total_items=0` 时无法计算百分比，前端显示 `--`，通知中 percent=0；属预期。
3. 管道进度以自身 `progress` 字段为百分比来源；进度不更新时周期消息仍会发（保活提醒）。
4. D-13 的函数级覆盖率（`pilotstd/scan`、`docker/api`）仍是长期项，与本功能无关。

## 六、回滚方式

1. 配置层：将 `notification.progress_interval_minutes` 设为 10，或在通知策略里关闭
   `task_progress` 类别，即可停止推送（不改代码）。
2. 代码层：回滚 `fix/feat(notify): D-2 ...` 相关提交；事件规格与调度器注册会一并回退。
3. 阶段即时回调失败只记 warning，不影响管道主流程（可单独移除 `on_step_changed` 注入）。
