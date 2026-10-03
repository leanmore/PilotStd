# 模块：项目/核心//_管理器_运维接口脚本
"""NotificationManager 的日志与运维接口（组合式实现，由 NotificationManager 持有）。

拆出原因（G-010 文件规模治理）：manager.py 有效行已两次逼近硬线——第一次 487（警告区）
拆出「写发送日志 / 日志分页查询 / 已读标记 / 未读计数 / 过期清理」五方法；
第二次是阶段 2b-接入加入 `_apply_mapping` 后达到 **519（超过 500 阻断线）**，
再把「通知映射回填」一并拆到这里。两组方法都与「事件 → 渠道分发」主流程
不共享任何局部状态（只依赖宿主、DB 与纯函数投影）。

为什么是组合而不是继承：`tests/test_architecture_mixin_guard.py` 明令**除
_WindowLifecycleMixin（Qt 硬约束）外禁止新增 Mixin**，并指定用 Composition 替代（ADR-010）。
故这里是**不继承任何东西**的普通类，管理器在 __init__ 里建 `self.ops = NotificationOps(self)`。
第一版曾用 Mixin 换取“调用点零改动”，被上述守护测试拦下——**不要再改回继承**。

为什么持有宿主引用而不是拷贝 db：`_db` 经属性代理在**调用期**读取，才与拆分前
各方法体的语义一致（拆分要求函数体逐字节不变）。
（原此处举的例子是"可重绑的 `_ws_broadcast`"——该属性随 WebSocket 死代码清理
于阶段 0 删除，见 docs/plans/notification-redesign/06-阶段0-1实施方案.md §1.2。）
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..db import Database
from . import _json_codec
from .channel import NotificationMessage
from .mapping import project
from .specs import specs_to_jsonable
from .stage import is_mapping_enabled

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
    # 阶段 1a 追加的 4 列（message_id / correlation_id / delivery_status / ack_status）、
    # 1b 的 4 列（task_id / notify_event / content_type / task_context）、
    # 1c 的 4 列（actions / callback_data / attachments / channel_message_ids）
    # 取 NotificationMessage 对应字段——故旧 11 列的取值与语义完全不变。
    # **非标量字段一律经 _json_codec 转换（唯一转换点）**：task_context /
    # channel_message_ids 走 dumps（dict），actions / attachments 先经
    # specs.specs_to_jsonable 转字典列表再 dumps（**不能**直接 dumps 规格对象）。
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
                "standard_number, status, error_msg, sent_at, aggregated_count, link, icon, "
                "message_id, correlation_id, delivery_status, ack_status, "
                "task_id, notify_event, content_type, task_context, "
                "actions, callback_data, attachments, channel_message_ids) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    msg.message_id,
                    msg.correlation_id,
                    msg.delivery_status,
                    msg.ack_status,
                    msg.task_id,
                    msg.notify_event,
                    msg.content_type,
                    _json_codec.dumps(msg.task_context),
                    _json_codec.dumps(specs_to_jsonable(msg.actions)),
                    msg.callback_data,  # 纯字符串，无需编解码
                    _json_codec.dumps(specs_to_jsonable(msg.attachments)),
                    _json_codec.dumps(msg.channel_message_ids),
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

    # ── 三层模型投影回填（阶段 2b-接入；默认不生效）────────────────────────────
    def apply_mapping(self, msg: NotificationMessage, event_type: str, event_data: dict[str, Any]) -> None:
        """回填三层模型的投影字段（`NotificationManager._apply_mapping` 的实现）。

        仅当 `stage.is_mapping_enabled()` 为真时执行（默认 False → 行为零变化）。
        回填两个**由查表唯一确定、且 `NotificationMessage` 已有**的字段：
        `notify_event` / `content_type`。

        未回填的三项及理由：
        - `task_kind`：`mapping.project()` 已产出，但 `NotificationMessage` **无该字段**
          （新增消息字段需同批加迁移/白名单/列，属独立批次）；
        - `correlation_id` / `task_context`：需 Task 实体投影（运行期上下文），属阶段 2b-启用/2.5。

        **失败不得影响主流程**：投影是旁路增强，异常只记 warning 并按未映射处理
        （与 `log()` 的静默失败、`_validate_message` 的"校验失败不崩主流程"同口径）。
        """
        if not is_mapping_enabled():
            return
        try:
            projection = project(event_type, event_data)
        except Exception as e:  # noqa: BLE001 — 投影失败不得吃掉通知
            # i18n-allow: 开发者日志（与 log()/渠道层既有告警同口径，不进 i18n）
            logger.warning("通知映射失败，按未映射处理: event=%s error=%s", event_type, e)
            return
        msg.notify_event = projection.notify_event
        msg.content_type = projection.content_type

