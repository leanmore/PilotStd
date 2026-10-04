"""防重放的**持久化**实现（阶段 B2b-2）。

裁决：B2b-2 "① 复用现有表（优先）—— grep 是否有合适的表可存 message_id + 时间戳"。

**选表与选列依据（实测）**：`notification_log` 已含 `channel` / `correlation_id` / `sent_at`，
足以承载"某渠道某事件号是否已处理 + 何时处理"：

- `correlation_id`：语义即"关联标识"，存放回调事件号最贴切（`message_id` 留给渠道消息号）；
- `event_type = 'callback'`：与投递日志（事件类型名）互不干扰，可按此过滤与清理；
- `status = 'processed'`：标记该行是"已处理"占位而非投递结果；
- `sent_at`：TTL 清理依据。

⇒ **不需要新建表、不需要加字段、不需要迁移号**（这正是裁决要求的优先路径）。
"""

import time
from datetime import datetime
from typing import Any

# 幂等窗口（秒）：覆盖渠道重投（Telegram 重试窗口、钉钉 3 次重投）后仍可清理
DEFAULT_WINDOW_SECONDS = 86400.0

_CALLBACK_EVENT_TYPE = "callback"
_PROCESSED_STATUS = "processed"


class LogBackedReplayGuard:
    """以 `notification_log` 为存储的防重放守卫（跨重启、跨 worker 幂等）。

    与 B2a 的进程内 `ReplayGuard` 同接口（`admit(channel, event_id, now)`），
    可互换使用；本实现用于**生产路径**，进程内实现仅作轻量场景/测试替身。
    """

    def __init__(self, db: Any, window_seconds: float = DEFAULT_WINDOW_SECONDS) -> None:
        self._db = db
        self.window_seconds = window_seconds

    def admit(self, channel: str, event_id: str, now: float | None = None) -> bool:
        """返回 True 表示首次到达；False 表示窗口内已处理过（应幂等忽略）。"""
        if not channel or not event_id:
            return False
        current = time.time() if now is None else now
        self._prune(current)
        rows = self._db.fetchall(
            "SELECT id FROM notification_log WHERE event_type = ? AND channel = ? "
            "AND correlation_id = ? LIMIT 1",
            (_CALLBACK_EVENT_TYPE, channel, event_id),
        )
        if rows:
            return False
        self._db.execute(
            "INSERT INTO notification_log (event_type, channel, title, body, status, "
            "error_msg, sent_at, correlation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _CALLBACK_EVENT_TYPE,
                channel,
                "",
                "",
                _PROCESSED_STATUS,
                "",
                # 与 `_prune` 同源：都用**本次判定时间**，注入时钟才可测（墙钟会让 TTL 失效）
                datetime.fromtimestamp(current).isoformat(),
                event_id,
            ),
        )
        return True

    def _prune(self, now: float) -> None:
        """清理超出窗口的占位行（避免表无限增长）。"""
        cutoff = datetime.fromtimestamp(now - self.window_seconds).isoformat()
        self._db.execute(
            "DELETE FROM notification_log WHERE event_type = ? AND sent_at < ?",
            (_CALLBACK_EVENT_TYPE, cutoff),
        )
