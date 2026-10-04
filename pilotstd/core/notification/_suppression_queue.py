# 模块：项目/核心//静音队列脚本
"""静音时段暂存与补发（步 C B1：从 `manager.py` 拆出）。

**为什么独立**：判静音 → 入队 → 到期补发是一条自洽的小链路，只依赖宿主的三样能力
（配置读取 / 数据库 / 发送实现）。留在管理器里会让它同时承担"编排"与"队列"两件事，
也让该模块的有效行数长期贴着 G-010 警告线。

**采用组合而非继承**（ADR-010；`tests/test_architecture_mixin_guard.py` 明令禁止新增
Mixin）：宿主构造本对象并注入三样能力，本模块不反向依赖管理器类型。

**发送实现必须"活的"**：`send_now` 由宿主以 `lambda` 形式传入（每次调用再取宿主的
`_send_now`），而不是在构造时取一次绑定方法——否则测试里 `mgr._send_now = ...` 的
替换不会生效（`tests/test_delivery_health.py` 的接线契约依赖这一点）。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable

from . import _json_codec
from .channel import NotificationMessage
from .specs import specs_to_jsonable

if TYPE_CHECKING:
    from pilotstd.core.db import Database

# 静音补发的**标量字段白名单**（唯一数据源）：写入侧与重建侧共用同一常量，
# 根治"两份字面量漂移"——新增字段只需改这里，两侧自动同步。
_QUEUE_MESSAGE_FIELDS = (
    "event_type",
    "title",
    "body",
    "level",
    "link",
    "icon",
    "message_id",
    "correlation_id",
    "delivery_status",
    "ack_status",
    # 阶段 1b：任务视角（task_context 是 dict，落库/还原由 _json_codec 负责，
    # 故它虽在 JSON 里但**不**列入本标量白名单——见 rebuild_message）
    "task_id",
    "notify_event",
    "content_type",
    # 阶段 1c：callback_data 是**字符串**，属标量 → 入白名单；
    # actions / attachments（规格列表）与 channel_message_ids（dict）走 _json_codec，不入此表
    "callback_data",
    # 阶段 2.5a：task_kind 是字符串（标量）→ 入白名单。**漏了它就会在静音补发时静默丢失**
    # ——与 1a/1b/1c 三批同一类缺陷（写入/重建两侧必须同源）
    "task_kind",
)


class SuppressionQueue:
    """静音时段暂存与补发（组合式：宿主注入配置、数据库与发送实现）。"""

    def __init__(
        self,
        config: Any,
        db: Database,
        send_now: Callable[[NotificationMessage, list[str]], None],
    ) -> None:
        """入参：配置读取器（点分隔键）/ 数据库封装 / 发送实现（宿主回调）。"""
        self._cfg = config
        self._db = db
        self._send_now = send_now

    def is_quiet_hours(self) -> bool:
        """检查当前是否在静音时段内（跨天支持 22:00-07:00）。"""
        if not self._cfg.get("notification.quiet_hours_enabled", False):
            return False
        now = datetime.now().time()
        start_str = self._cfg.get("notification.quiet_hours_start", "22:00")
        end_str = self._cfg.get("notification.quiet_hours_end", "07:00")
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
        if start <= end:
            return start <= now <= end
        else:
            return now >= start or now <= end

    def enqueue(self, msg: NotificationMessage, target_channels: list[str]) -> str:
        """静音时段内暂存通知到 notification_queue 表；返回计划补发时刻（ISO 文本）。

        **日志文案留在宿主**：G-047 对"不在存量基线中的新文件"要求零中文硬编码，
        而这两条日志原本是中文——故本模块只返回数据，由宿主（在基线内）记录日志，
        日志文本与拆分前逐字一致。
        """
        end_str = self._cfg.get("notification.quiet_hours_end", "07:00")
        hour, minute = map(int, end_str.split(":"))
        now = datetime.now()
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= scheduled:
            scheduled += timedelta(days=1)
        event_data = json.dumps(
            {
                # 写入键集合由 _QUEUE_MESSAGE_FIELDS 驱动（**唯一数据源**）：
                # 与重建侧共用同一常量，根治"两份字面量漂移"——新增字段只需改常量，
                # 两侧自动同步（阶段 1a 起；1b 加入任务视角 3 字段；1c 加入 callback_data）。
                **{f: getattr(msg, f) for f in _QUEUE_MESSAGE_FIELDS},
                # 非标量字段单独走编解码模块转 JSON 文本（SQLite 无原生 JSON 类型）：
                # task_context / channel_message_ids 是 dict；actions / attachments 是规格列表，
                # 先经 specs_to_jsonable 转字典列表再序列化（不能直接 dumps 规格对象）。
                "task_context": _json_codec.dumps(msg.task_context),
                "actions": _json_codec.dumps(specs_to_jsonable(msg.actions)),
                "attachments": _json_codec.dumps(specs_to_jsonable(msg.attachments)),
                "channel_message_ids": _json_codec.dumps(msg.channel_message_ids),
                "channels": target_channels,
            },
            ensure_ascii=False,
        )
        self._db.execute(
            "INSERT INTO notification_queue (event_type, event_data, status, scheduled_time, created_at) "
            "VALUES (?, ?, 'suppressed', ?, ?)",
            (msg.event_type, event_data, scheduled.isoformat(), now.isoformat()),
        )
        return scheduled.isoformat()

    def rebuild_message(self, data: dict) -> tuple[NotificationMessage, list[str]]:
        """按白名单从落库 JSON 重建消息与目标渠道（补发路径的唯一重建入口）。"""
        channels = data.pop("channels", [])
        # 白名单重建：**必须**与 enqueue 的写入键保持一致，
        # 否则新字段在补发路径被静默丢弃（只在静音时段暴露，最难发现）。
        # 契约由 tests/test_notification_stage1b_fields.py::TestQueueJsonRoundTrip 锁定。
        fields = {k: v for k, v in data.items() if k in _QUEUE_MESSAGE_FIELDS}
        # 非标量字段逐个还原（都经 _json_codec，空值/非法输入一律回退空容器，
        # 保证字段类型恒定：dict 恒 dict、list 恒 list，不会变成 None）。
        fields["task_context"] = _json_codec.loads_dict(data.get("task_context"))
        fields["actions"] = _json_codec.loads_list(data.get("actions"))
        fields["attachments"] = _json_codec.loads_list(data.get("attachments"))
        fields["channel_message_ids"] = _json_codec.loads_dict(data.get("channel_message_ids"))
        return NotificationMessage(**fields), channels

    def release(self) -> tuple[int, list[str]]:
        """补发所有已到期的压制通知，返回（补发条数, 失败明细）。

        失败明细交宿主记录日志（同 enqueue 的口径：日志文案留在基线内的宿主模块）。
        """
        now = datetime.now().isoformat()
        rows = self._db.fetchall(
            "SELECT id, event_type, event_data FROM notification_queue "
            "WHERE status='suppressed' AND scheduled_time <= ?",
            (now,),
        )
        if not rows:
            return 0, []
        failures: list[str] = []
        for row in rows:
            self._db.execute("UPDATE notification_queue SET status='sending' WHERE id=?", (row["id"],))
            try:
                msg, channels = self.rebuild_message(json.loads(row["event_data"]))
                self._send_now(msg, channels)
                self._db.execute("UPDATE notification_queue SET status='sent' WHERE id=?", (row["id"],))
            except Exception as e:
                failures.append(str(e))
                self._db.execute(
                    "UPDATE notification_queue SET status='failed', error_msg=? WHERE id=?",
                    (str(e), row["id"]),
                )
        return len(rows), failures
