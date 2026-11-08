# 通知实施阶段契约（阶段 2 / 2.5）

> 本文从 `docs/plans/notification-redesign/03-实施路径.md` §3.2 / §3.3 提炼；设计过程原文已归档，见 `docs/architecture/notification-system.md`。

## 一、`task_kind` 双 SSOT 与单向翻译（**阶段 2.5 必做项**）

### 1.1 两个 SSOT

| 视角 | 字段 | 回答的问题 | 值域来源 |
|------|------|------------|----------|
| 通知视角 | `task_kind` | 用户交办的是哪类事 | `pilotstd/core/notification/mapping.py::TASK_KINDS` |
| 执行队列视角 | `task_type` | 哪个任务在跑 | `pilotstd/task/models.py::TaskType` |

- `TASK_KINDS`（当前 10 个业务域名词）：`announce_fetch` / `scan` / `query` / `organize` / `normalize` / `favorite_download` / `validity_check` / `backup` / `image_update` / `auto_pipeline`。
- `TaskType`（5 个执行队列类型）：`scan` / `query` / `download` / `organize` / `expire`。
- 两侧**不同轴**，交集仅 `scan` / `query` / `organize`；一个任务名可产出多个 `task_kind` 的通知，一个 `task_kind` 也可被多个任务写。

### 1.2 单向翻译（**双 SSOT**，不提供反向函数）

`mapping.TASK_KIND_TO_TASK_TYPE` + `task_kind_to_task_type()` 只做 `task_kind → task_type` 的**单向**翻译：

| `task_kind` | `task_type` | 说明 |
|---|---|---|
| `scan` | `scan` | 同名同义 |
| `query` | `query` | 同名同义 |
| `organize` | `organize` | 同名同义 |
| `favorite_download` | `download` | 收藏下载是最常用的下载语义 |
| `announce_fetch` | `query` | 公告抓取由查询侧适配器执行 |
| `normalize` | `organize` | 规范化是归档整理链的一步 |
| `validity_check` | `query` | 时效性核查走站点查询 |
| `backup` | `organize` | 备份由整理侧定时任务承担 |
| `image_update` | `organize` | 镜像更新无独立队列类型 |
| `auto_pipeline` | `scan` | 一键处理跨四阶段，归入触发它的首个阶段（Q11 裁决） |

**约定**：

- **只做单向**（`task_kind → task_type`），**不提供反向函数**——反向是“一对多”（如 `query` 可来自 `query` 或 `announce_fetch`），强行反向必然要猜。
- 未知 `task_kind`（含空串）返回 `""`，调用方据此跳过翻译，而不是猜一个值。
- 已知缺口：`TaskType.expire` 没有对应的 `task_kind`（无“到期处理”类通知语义），由 `TestTaskKindMappingTable::test_known_gap_is_documented` 显式记录。

### 1.3 落地状态（阶段 2.5a）

- `NotificationMessage.task_kind: str = ""` 已是消息字段；
- 已进 `_QUEUE_MESSAGE_FIELDS`（静音补发白名单）；
- `notification_log.task_kind TEXT NOT NULL DEFAULT ''` 由迁移 v65 建列；
- 写入侧 `_manager_ops.py` 的 INSERT 已包含 `task_kind`，读取侧按标量回填。

## 二、源码位置

| 契约 | 文件与行号 |
|------|------------|
| `TASK_KINDS` | `pilotstd/core/notification/mapping.py:101-112` |
| 双 SSOT 约定注释 | `mapping.py:168-181` |
| `TASK_KIND_TO_TASK_TYPE` | `mapping.py:182-198` |
| `task_kind_to_task_type()` | `mapping.py:201-209` |
| `project()` 回填 `task_kind` | `mapping.py:230-234` |
| `NotificationMessage.task_kind` | `pilotstd/core/notification/channel.py:83` |
| `_QUEUE_MESSAGE_FIELDS`（含 `task_kind`） | `pilotstd/core/notification/_suppression_queue.py:53-55` |
| INSERT 列与值 | `pilotstd/core/notification/_manager_ops.py:80`、`:108-109` |
| 迁移 v65 建列 | `pilotstd/core/db/_migrate_v65_notification_log_task_kind.py:19-23` |
| `TaskType` 值域 | `pilotstd/task/models.py:8-15` |

## 三、测试锚点

| 测试 | 说明 |
|------|------|
| `tests/test_notification_stage2b_wiring.py:337` | `test_task_kind_now_a_message_field`：消息字段 + 队列白名单 |
| `:346` | `TestTaskKindPersisted`：2.5a 翻转后的“必须落库”断言 |
| `:354` / `:362` / `:368` / `:375` | INSERT 列 / 队列白名单 / 消息字段 / 表列 TEXT |
| `:393` | `test_consume_point_documented_in_sources`：读本文件，断言出现 `阶段 2.5 必做项` 与 `双 SSOT` |
| `:408` | `TestTaskKindMappingTable`：单向映射表覆盖、未知值回退、已知缺口 |
| `tests/test_notification_stage2a_mapping.py` | 投影/映射侧回归（阶段 2a） |
