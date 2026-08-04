# 模块：pilotstd/core/notification/_policy.py
# 通知策略表读写 Helper — 从 manager.py 拆分以控制文件规模

import json as _json
from typing import Any

_CHANNEL_CLASSES = ("wechat", "telegram", "feishu", "dingtalk")


class NotificationPolicyHelper:
    """通知策略表读写辅助类（组合模式，非 Mixin）。

    由 NotificationManager 实例化，传入 _db 和 _cfg 引用。
    """

    def __init__(self, db: Any, cfg: Any) -> None:
        self._db = db
        self._cfg = cfg

    def get_channels_for_event(self, user_id: int, event_type: str) -> list[str]:
        """从 notification_policy 表查询该事件应发送到哪些渠道（按用户隔离）。"""
        try:
            rows = self._db.fetchall(
                'SELECT "channel", "events" FROM "notification_policy" WHERE "user_id"=? AND "enabled"=1',
                (user_id,),
            )
            if rows:
                channels = []
                for r in rows:
                    events = _json.loads(r["events"]) if r["events"] else []
                    if event_type in events:
                        channels.append(r["channel"])
                if channels:
                    return channels
        except Exception:
            pass

        # 回退：从 config.json 读取旧版 rules
        rules = self._cfg.get(f"notification.rules.{event_type}")
        if not rules:
            return []
        if isinstance(rules, str):
            return [c.strip() for c in rules.split(",") if c.strip()]
        return rules

    def get_policies(self, user_id: int) -> list[dict[str, Any]]:
        """返回某用户的全部策略。"""
        rows = self._db.fetchall(
            'SELECT "id", "channel", "enabled", "events", "updated_at" FROM "notification_policy"'
            ' WHERE "user_id"=? ORDER BY "channel"',
            (user_id,),
        )
        result: list[dict[str, Any]] = []
        for r in rows:
            result.append(
                {
                    "id": r["id"],
                    "channel": r["channel"],
                    "enabled": bool(r["enabled"]),
                    "events": _json.loads(r["events"]) if r["events"] else [],
                    "updated_at": r["updated_at"],
                }
            )
        return result

    def save_policy(self, user_id: int, channel: str, enabled: bool | None, events: list[str] | None) -> None:
        """更新或插入某用户的策略。"""
        existing = self._db.fetchone(
            'SELECT "id" FROM "notification_policy" WHERE "user_id"=? AND "channel"=?',
            (user_id, channel),
        )
        if existing:
            if enabled is not None:
                self._db.execute(
                    'UPDATE "notification_policy" SET "enabled"=?, "updated_at"=CURRENT_TIMESTAMP WHERE "id"=?',
                    (1 if enabled else 0, existing["id"]),
                )
            if events is not None:
                self._db.execute(
                    'UPDATE "notification_policy" SET "events"=?, "updated_at"=CURRENT_TIMESTAMP WHERE "id"=?',
                    (_json.dumps(events, ensure_ascii=False), existing["id"]),
                )
        else:
            self._db.execute(
                'INSERT INTO "notification_policy" ("user_id", "channel", "enabled", "events") VALUES (?, ?, ?, ?)',
                (
                    user_id,
                    channel,
                    1 if (enabled is None or enabled) else 0,
                    _json.dumps(events or [], ensure_ascii=False),
                ),
            )
