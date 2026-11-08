# 通知字段契约（stage 1c）

> 本文是从 `docs/plans/notification-redesign/02-目标架构.md` §2.2 提炼的稳定契约。
> 设计过程原文（三层分离、渠道能力矩阵等）已归档，见 `docs/architecture/notification-system.md`。

## 一、字段清单

`NotificationMessage` 在阶段 1a~1c 追加以下字段，全部带默认值，零调用点改动：

| 新字段 | 类型 | 默认 | 语义 | 为什么必需 |
|--------|------|------|------|-----------|
| `message_id` | `str` | `""` | 通知消息的稳定 ID（`uuid4().hex[:16]` 或 `corr-seq`） | 回调要能定位消息；`notification_log.id` 是行号，不能反查渠道消息 |
| `correlation_id` | `str` | `""` | 同一次业务运行的关联键（如“2026-10-02 收藏链第 3 批”） | 让 N 条通知在数据层可归组；现状只能靠 `standard_number` 事后猜 |
| `task_id` | `str` | `""` | 关联 Task 实体（见 §2.3） | 进度型通知的原地更新锚点 |
| `notify_event` | `str` | `""` | 三层模型中的通知事件（`task_progress`／`task_result`／`task_failure` 等 10 类之一；清单以 `event_spec.py` 为准） | 路由/配置/治理的新粒度；为空时回退用 `event_type` 推导（阶段 1–3 兼容） |
| `content_type` | `str` | `""` | 主内容类型（6 种之一） | 渲染降级与“该不该发”的策略判断依据 |
| `delivery_status` | `str` | `"pending"` | `pending`/`sent`/`failed`/`suppressed`/`edited` | **刻意不复用现有 `status` 字段**（后者是业务结果态 `success`/`failure`，见 Q3 裁决） |
| `ack_status` | `str` | `"none"` | `none`/`delivered`/`read`/`acted` | 交互闭环的落点；现状渠道契约只有 `-> bool`，无法表达“用户点过” |
| `actions` | `list[ActionSpec]` | `[]` | 可交互动作声明（见下） | 按钮的唯一数据源 |
| `callback_data` | `str` | `""` | 回调载荷（编码后 ≤ 64 字节，见 §2.4） | 渠道对回调数据有长度限制 |
| `attachments` | `list[AttachmentSpec]` | `[]` | 图片/文件附件（`kind`/`url`/`name`/`size`） | 现状无任何附件通道；实测四渠道均无图片发送代码 |
| `task_context` | `dict[str, Any]` | `{}` | 任务上下文快照（Task/TaskItem/TaskProgress 的扁平投影） | 让“任务视角”的通知不必把语义塞进 `event_type` |
| `channel_message_ids` | `dict[str, str]` | `{}` | 渠道名 → 该渠道返回的消息 ID | 消息编辑的唯一凭据；**留空即表示该渠道不支持编辑** |

> **范围说明**：本表是 02 §2.2 定义的 12 个新增字段。后续阶段在 `channel.py` 追加的
> `failed_items`（B1）、`task_kind`（阶段 2.5a）、`user_id`/`delivery_user_id`（A-21）
> 不在本表；它们的契约分别由对应阶段文档与测试锁定。

### `channel_message_ids` 语义约定（阶段 1c 已落地，见 `channel.py::CHANNEL_KEY_WHITELIST`）

> ① 键必须取自渠道白名单 `{wechat, dingtalk, feishu, telegram}`——**桌面与 Web 不计入**
> （桌面 `QSystemTrayIcon.showMessage` 无消息句柄、Web 无后端推送通道）；
> ② 值恒为**该渠道返回的消息 ID 字符串**；
> ③ **未投递的渠道用“键缺席”表达，不是 `{"wechat": None}`**
> （值类型恒为 `str`，读取方不必处理 `None`）；
> ④ 将来新增渠道时，白名单与 `channels/` 实现必须**同批**扩展。

### 动作白名单（`ActionSpec.action` 的闭集）

| 动作 | 语义 | 改变状态？ | 最低权限 | 支持渠道 |
|------|------|-----------|---------|---------|
| `view_detail` | 打开站内详情/日志 | 否 | 接收者 | 全渠道（无按钮时降级为链接） |
| `open_logs` | 打开通知日志页 | 否 | 接收者 | 全渠道（同上） |
| `retry` | 重试失败项（写 `task_queue`） | **是** | 管理员 | 仅交互渠道 |
| `ignore` | 忽略/确认（记录 `ack_status=acted`） | 否（仅回执） | 接收者 | 仅交互渠道 |
| `snooze` | 稍后提醒（写延后队列） | **是**（延迟） | 接收者 | 仅交互渠道 |
| `mark_done` | 人工标记完成 | **是** | 管理员 | 仅交互渠道 |

### 相关规格类型

| 类型 | 字段 | 源码 |
|------|------|------|
| `ActionSpec`（`actions` 元素） | `action` / `label_key` / `style`（默认 `default`）/ `args`（默认 `{}`）/ `requires_confirm`（默认 `False`） | `specs.py:57-74` |
| `AttachmentSpec`（`attachments` 元素） | `kind` / `url` / `name`（默认 `""`）/ `size`（默认 `0`） | `specs.py:80-86` |

## 二、源码位置

| 契约 | 文件与行号 |
|------|------------|
| `NotificationMessage` 类 | `pilotstd/core/notification/channel.py:33` |
| 身份/生命周期字段（`message_id`/`correlation_id`/`delivery_status`/`ack_status`） | `channel.py:54-60` |
| 任务视角字段（`task_id`/`notify_event`/`content_type`/`task_context`） | `channel.py:64-93` |
| 交互字段（`actions`/`callback_data`/`attachments`/`channel_message_ids`） | `channel.py:99-108` |
| `CHANNEL_KEY_WHITELIST` | `channel.py:19-29` |
| `CHANNEL_NAMES` 声明源 | `channel_spec_data.py:414`；再导出 `channel_spec.py:219-220` |
| 动作/附件白名单与规格 | `specs.py:40-53`（`ACTIONS`/`ACTION_STYLES`/`ATTACHMENT_KINDS`）、`:57` `ActionSpec`、`:80` `AttachmentSpec` |
| 落库/回填列 | `_manager_ops.py:51-56`（列）、`:94-107`（写入）、`_suppression_queue.py:41-51`（持久化字段）、`:154`（回填） |

## 三、测试锚点

| 测试 | 说明 |
|------|------|
| `tests/test_notification_stage1c_fields.py:413` | `TestChannelMessageIdsContract` 类 |
| `:416` | `test_key_whitelist`：spec 必须恰好声明 4 个已知渠道 |
| `:430` | `test_spec_classes_match_real_implementations`：AST 比对声明类与实现类 |
| `:454` | `test_missing_channel_means_key_absent_not_none`：键缺席而不是 `None` |
| `:461` | `test_contract_documented_in_source_and_doc`：读本文件并断言出现 `channel_message_ids` |
| `:85` | `test_action_whitelist_matches_design`：`ACTIONS` 六项闭集 |
