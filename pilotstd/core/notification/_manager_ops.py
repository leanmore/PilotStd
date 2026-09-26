# 模块：项目/核心//_管理器_运维接口脚本
"""NotificationManager 的日志与运维接口（组合式实现，由 NotificationManager 持有）。

拆出原因（G-010 文件规模治理）：manager.py 有效行 487 已进入警告区，而本组方法
（写发送日志 / 日志分页查询 / 已读标记 / 未读计数 / 过期清理 / WebSocket 广播）
与「事件 → 渠道分发」主流程不共享任何局部状态。

为什么是组合而不是继承：`tests/test_architecture_mixin_guard.py` 明令**除
_WindowLifecycleMixin（Qt 硬约束）外禁止新增 Mixin**，并指定用 Composition 替代（ADR-010）。
故这里是**不继承任何东西**的普通类，管理器在 __init__ 里建 `self.ops = NotificationOps(self)`。
第一版曾用 Mixin 换取“调用点零改动”，被上述守护测试拦下——**不要再改回继承**。

为什么持有宿主引用而不是拷贝 db/ws_broadcast：`_ws_broadcast` 是**可重绑**属性
（`tests/test_notification_manager.py::TestWSBroadcast` 先构造管理器、再改该属性、最后调用广播），
只有调用期读取才与拆分前的语义一致；`_db` 同理经属性代理转发。
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..db import Database
from .channel import NotificationMessage

if TYPE_CHECKING:
    from .manager import NotificationManager

logger = logging.getLogger(__name__)


class NotificationOps:
    """通知日志与运维接口（组合进 NotificationManager，不做继承）。"""

    def __init__(self, manager: "NotificationManager"):
        self._mgr = manager

    @property
    def _db(self) -> Database:
        """宿主数据库连接（调用期读取，保持拆分前各方法体逐字节不变）。"""
        return self._mgr._db

    # 写发送日志：刻意静默失败——日志落库不该反向影响通知投递本身，故只记 warning；
    # aggregated_count / link / icon 三列用于还原“这条代表合并了多少条事件”。
    def log(
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

    # 分页查询：筛选条件按需拼接（列名是固定字面量、值一律走参数占位符），
    # total 与 items 共用同一个 WHERE，避免“筛选后条数对不上”的经典分页缺陷。
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

    # ids 为空表示“全部标记已读”，此时返回 0——调用方据此区分“按条计数”与“全量操作”。
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

    # 保留期清理：sent_at 存的是 ISO 字符串，字典序即时间序，故可直接用字符串比较做截止点；
    # 仅在实际删除时记 INFO，避免每天一条“清理了 0 条”的噪声。
    def cleanup_logs(self, days: int = 30) -> int:
        """删除 days 天前的通知日志，返回删除条数。"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        cur = self._db.execute("DELETE FROM notification_log WHERE sent_at < ?", (cutoff,))
        deleted = cur.rowcount
        if deleted > 0:
            logger.info("清理了 %d 条过期通知日志（保留 %d 天）", deleted, days)
        return deleted

    def broadcast_to_ws(self, event_type: str, msg: NotificationMessage) -> None:
        """通过独立线程向 WebSocket 连接广播通知消息（非阻塞）。"""
        callback = self._mgr._ws_broadcast  # 调用期读取：该属性可被重绑（见 TestWSBroadcast）
        if callback is None:
            return

        import threading

        # 通过回调注入执行广播（回调内部处理/细节）
        threading.Thread(
            target=callback,
            args=(event_type, msg.title, msg.body, msg.level, msg.link, msg.icon, msg.aggregated_count),
            daemon=True,
            name="notif-ws-broadcast",
        ).start()

