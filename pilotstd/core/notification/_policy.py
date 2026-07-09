# pilotstd/core/notification/_policy.py
# 通知策略表读写 Helper — 从 manager.py 拆分以控制文件规模

import json
from typing import Any

_CHANNEL_CLASSES = ("wechat", "telegram", "feishu", "dingtalk")


class NotificationPolicyHelper:
    """通知策略表读写辅助类（组合模式，非 Mixin）。

    由 NotificationManager 实例化，传入 _db 和 _cfg 引用。
    """

    def __init__(self, db: Any, cfg: Any) -> None:
        self._db = db
        self._cfg = cfg

    def get_channels_for_event(self, event_type: str) -> list[str]:
        """从 notification_policy 表查询该事件应发送到哪些渠道。"""
        try:
            rows = self._db.fetchall(
                "SELECT channel, events FROM notification_policy WHERE (user_id IS NULL) AND enabled = 1"
            )
            if rows:
                channels = []
                for r in rows:
                    events = json.loads(r["events"]) if r["events"] else []
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

    def get_policies(self) -> list[dict[str, Any]]:
        """返回所有系统默认策略（user_id IS NULL）。"""
        rows = self._db.fetchall(
            "SELECT id, channel, enabled, events, updated_at FROM notification_policy"
            " WHERE user_id IS NULL ORDER BY channel"
        )
        result: list[dict[str, Any]] = []
        for r in rows:
            result.append(
                {
                    "id": r["id"],
                    "channel": r["channel"],
                    "enabled": bool(r["enabled"]),
                    "events": json.loads(r["events"]) if r["events"] else [],
                    "updated_at": r["updated_at"],
                }
            )
        # 如果表为空，回退到 config.json 构建默认策略
        if not result:
            for ch_name in _CHANNEL_CLASSES:
                events: list[str] = []
                for key in self._cfg._data:
                    if key.startswith("notification.rules.") and ch_name in (self._cfg._data[key] or []):
                        events.append(key[len("notification.rules.") :])
                result.append(
                    {
                        "id": 0,
                        "channel": ch_name,
                        "enabled": self._cfg.get(f"notification.channels.{ch_name}.enabled", True),
                        "events": sorted(events),
                        "updated_at": "",
                    }
                )
        return result

    def save_policy(self, channel: str, enabled: bool | None, events: list[str] | None) -> None:
        """更新或插入系统默认策略（user_id IS NULL）。"""
        existing = self._db.fetchone(
            "SELECT id FROM notification_policy WHERE user_id IS NULL AND channel=?", (channel,)
        )
        if existing:
            if enabled is not None:
                self._db.execute(
                    "UPDATE notification_policy SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (1 if enabled else 0, existing["id"]),
                )
            if events is not None:
                self._db.execute(
                    "UPDATE notification_policy SET events=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (json.dumps(events, ensure_ascii=False), existing["id"]),
                )
        else:
            self._db.execute(
                "INSERT INTO notification_policy (user_id, channel, enabled, events) VALUES (NULL, ?, ?, ?)",
                (channel, 1 if (enabled is None or enabled) else 0, json.dumps(events or [], ensure_ascii=False)),
            )
