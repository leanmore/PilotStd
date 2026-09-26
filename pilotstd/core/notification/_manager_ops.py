# 模块：项目/核心//_管理器_运维接口脚本
"""NotificationManager 的日志与运维接口（Mixin，由 NotificationManager 混入）。

拆出原因（G-010 文件规模治理）：manager.py 有效行 487 已进入警告区，而本组方法
（写发送日志 / 日志分页查询 / 已读标记 / 未读计数 / 过期清理 / WebSocket 广播）
与「事件 → 渠道分发」主流程不共享任何局部状态，只依赖 self._db 与 self._ws_broadcast；
按 ADR-010 已接受的 Mixin 模式整体外移，主流程文件只剩分发与聚合装配。

为什么是 Mixin 而不是模块级函数：这些方法是对外契约——docker/api/notification.py、
docker/scheduler.py 与 tests/test_notification_manager.py 都直接调用 nmgr.get_logs() 等，
Mixin 让签名与全部调用点一个字符都不用改。

属性注解的用途：本 Mixin 不定义 __init__，_db / _ws_broadcast 由
NotificationManager.__init__ 赋值；不在此声明则 mypy 报 attr-defined（core 目录没有
pilotstd.ui.* 那样的 ignore_errors 豁免）。
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from ..db import Database
from .channel import NotificationMessage

logger = logging.getLogger(__name__)


class _NotificationOpsMixin:
    """通知日志与运维接口（依赖宿主提供 _db 与 _ws_broadcast）。"""

    _db: Database
    _ws_broadcast: Callable[..., Any] | None

    def _log(
        self,
        event_type: str,
        channel: str,
        msg: NotificationMessage,
        status: str,
        error_msg: str,
        sent_at: str,
    ) -> None:
        """写入通知发送日志到 notification_log 表（静默失败）。"""
        try:
            self._db.execute(
                "INSERT INTO notification_log (event_type, channel, title, body, "
                "standard_number, status, error_msg, sent_at, aggregated_count, link, icon) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_type,
                    channel,
                    msg.title,
                    msg.body,
                    msg.standard_number,
                    status,
                    error_msg,
                    sent_at,
                    msg.aggregated_count,
                    msg.link,
                    msg.icon,
                ),
            )
        except Exception as e:
            logger.warning("通知日志写入失败: %s", e)

    def _broadcast_to_ws(self, event_type: str, msg: NotificationMessage) -> None:
        """通过独立线程向 WebSocket 连接广播通知消息（非阻塞）。"""
        if self._ws_broadcast is None:
            return

        import threading

        # 通过回调注入执行广播（回调内部处理/细节）
        threading.Thread(
            target=self._ws_broadcast,
            args=(event_type, msg.title, msg.body, msg.level, msg.link, msg.icon, msg.aggregated_count),
            daemon=True,
            name="notif-ws-broadcast",
        ).start()

    # ──公开查询方法（替代直接访问_）──────────────────────

    def get_logs(
        self,
        page: int = 1,
        size: int = 20,
        channel: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        is_read: bool | None = None,
    ) -> dict[str, Any]:
        """获取通知日志列表（分页 + 筛选），供 API 层调用。"""
        db = self._db
        conditions: list[str] = []
        params: list[Any] = []

        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if start_date:
            conditions.append("sent_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("sent_at <= ?")
            params.append(end_date)
        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if is_read else 0)

        where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        offset = (page - 1) * size

        total_row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM notification_log {where_sql}", tuple(params))
        rows = db.fetchall(
            f"SELECT * FROM notification_log {where_sql} ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            tuple(params + [size, offset]),
        )
        return {
            "items": rows,
            "total": total_row["cnt"] if total_row else 0,
            "page": page,
            "size": size,
        }

    def mark_logs_read(self, ids: list[int] | None = None) -> int:
        """标记通知日志为已读（单条或全部），供 API 层调用。"""
        db = self._db
        if ids:
            for i in ids:
                db.execute("UPDATE notification_log SET is_read = 1 WHERE id = ?", (i,))
            return len(ids)
        else:
            db.execute("UPDATE notification_log SET is_read = 1")
            return 0

    def get_unread_count(self) -> int:
        """获取未读通知数量。"""
        row = self._db.fetchone("SELECT COUNT(*) AS cnt FROM notification_log WHERE is_read = 0")
        return row["cnt"] if row else 0

    # ── 日志清理 ──────────────────────────────────────────────

    def cleanup_logs(self, days: int = 30) -> int:
        """删除 days 天前的通知日志，返回删除条数。"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        cur = self._db.execute("DELETE FROM notification_log WHERE sent_at < ?", (cutoff,))
        deleted = cur.rowcount
        if deleted > 0:
            logger.info("清理了 %d 条过期通知日志（保留 %d 天）", deleted, days)
        return deleted
