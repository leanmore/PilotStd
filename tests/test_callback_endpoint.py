"""阶段 B2b-1/B2b-2：回调闭环（端点 + 持久化幂等）。

设计依据：裁决 B2b（代码完整落地、配置留给部署）、
[03-实施路径.md](../../docs/plans/notification-redesign/03-实施路径.md) §3.4。
端到端（真实渠道回调）标注"部署后取证"。
"""

import base64
import hashlib
import hmac
import json
import sqlite3
from pathlib import Path

from pilotstd.core.notification.callback_service import handle_callback
from pilotstd.core.notification.callback_store import LogBackedReplayGuard

SECRET = "call-secret"
NOW = 1_700_000_000.0


class _Db:
    """把内存库包装成 `Database` 同款接口（fetchall 返回字典行）。"""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT, channel TEXT, title TEXT, body TEXT, standard_number TEXT,
                status TEXT, error_msg TEXT, sent_at TEXT, is_read INTEGER DEFAULT 0,
                aggregated_count INTEGER DEFAULT 1, link TEXT, icon TEXT, message_id TEXT,
                correlation_id TEXT, delivery_status TEXT, ack_status TEXT DEFAULT '',
                task_id TEXT, notify_event TEXT, content_type TEXT, task_context TEXT,
                actions TEXT, callback_data TEXT, attachments TEXT,
                channel_message_ids TEXT, task_kind TEXT
            );
            -- 与生产 users 表列集一致（Schema 一致性门禁要求测试表不得缺列）
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                password_hash TEXT,
                salt TEXT,
                role TEXT,
                must_change_password INTEGER DEFAULT 0,
                created_at TEXT
            );
            """
        )
        self.conn.commit()

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self.conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        self.conn.commit()
        return rows

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple = ()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def seed_notification(self, log_id: int = 7, user_id: int = 1, channel: str = "telegram") -> str:
        """插入一条"已发出、可被回调操作"的通知，返回按钮 token。"""
        self.execute(
            "INSERT INTO notification_log"
            " (id, event_type, channel, title, body, status, sent_at, ack_status, callback_data)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                log_id,
                "scan_complete",
                channel,
                "标题",
                "正文",
                "success",
                "2026-10-03T00:00:00",
                "",
                "",
            ),
        )
        self.execute(
            "INSERT OR REPLACE INTO users (id, username, role) VALUES (?, ?, ?)",
            (user_id, "u", "admin"),
        )
        return f"{log_id}:{user_id}"


def _telegram_body(action: str = "ignore", token: str = "7:1", event_id: str = "tg-evt-1") -> bytes:
    payload = {"callback_query": {"id": event_id, "data": f"{action}:{token}", "from": {"id": 42}}}
    return json.dumps(payload).encode("utf-8")


def _telegram_headers(secret: str = SECRET) -> dict[str, str]:
    return {"X-Telegram-Bot-Api-Secret-Token": secret}


def _dingtalk_body(action: str = "ignore", token: str = "7:1") -> bytes:
    return json.dumps({"action": action, "outTrackId": token, "userId": "u1"}).encode("utf-8")


def _dingtalk_headers(secret: str = SECRET) -> dict[str, str]:
    stamp = str(int(NOW * 1000))
    raw = hmac.new(secret.encode(), f"{stamp}\n{secret}".encode(), hashlib.sha256).digest()
    return {"timestamp": stamp, "sign": base64.b64encode(raw).decode()}


def _creds(user_id: int, channel: str) -> dict[str, str]:
    return {"secret": SECRET}


class TestCallbackService:
    def _handle(self, db, channel="telegram", headers=None, body=None, guard=None):
        return handle_callback(
            db,
            channel,
            headers if headers is not None else _telegram_headers(),
            body if body is not None else _telegram_body(),
            _creds,
            now=NOW,
            guard=guard,
        )

    def test_unknown_token_rejected(self):
        db = _Db()
        db.seed_notification(log_id=7)
        outcome = self._handle(db, body=_telegram_body(token="999:1"))
        assert outcome.status == 401

    def test_bad_signature_rejected(self):
        db = _Db()
        db.seed_notification()
        outcome = self._handle(db, headers=_telegram_headers("wrong"))
        assert outcome.status == 401

    def test_non_admin_forbidden(self):
        db = _Db()
        db.seed_notification()
        db.execute("UPDATE users SET role = ? WHERE id = 1", ("user",))
        outcome = self._handle(db)
        assert outcome.status == 403

    def test_admin_ignore_updates_ack_status(self):
        db = _Db()
        db.seed_notification()
        outcome = self._handle(db)
        assert outcome.status == 200 and outcome.payload["ok"] is True
        row = db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")
        assert row["ack_status"] == "ignored"

    def test_snooze_and_retry_paths(self):
        db = _Db()
        db.seed_notification()
        assert self._handle(db, body=_telegram_body(action="snooze", event_id="e-s")).status == 200
        assert db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")["ack_status"] == "snoozed"
        assert self._handle(db, body=_telegram_body(action="retry", event_id="e-r")).status == 200
        assert db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")["ack_status"] == "retry_requested"

    def test_replay_is_idempotent(self):
        """同一事件号第二次到达：返回 200，但**动作不重复执行**。"""
        db = _Db()
        db.seed_notification()
        first = self._handle(db)
        assert first.status == 200
        db.execute("UPDATE notification_log SET ack_status = '' WHERE id = 7")
        second = self._handle(db)
        assert second.status == 200
        assert second.reason_key == "notification.callback.replayed"
        assert db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")["ack_status"] == ""

    def test_unknown_action_forbidden(self):
        db = _Db()
        db.seed_notification()
        outcome = self._handle(db, body=_telegram_body(action="boom"))
        assert outcome.status == 403

    def test_dingtalk_channel_round_trip(self):
        db = _Db()
        db.seed_notification(channel="dingtalk")
        outcome = handle_callback(
            db, "dingtalk", _dingtalk_headers(), _dingtalk_body(), _creds, now=NOW
        )
        assert outcome.status == 200

    def test_wechat_channel_rejected(self):
        db = _Db()
        db.seed_notification(channel="wechat")
        outcome = handle_callback(
            db, "wechat", {}, _telegram_body(token="7:1"), _creds, now=NOW
        )
        assert outcome.status in (401, 501)


class TestPersistentReplayGuard:
    def test_admit_persists_across_instances(self):
        """跨实例（等价于跨重启/跨 worker）幂等：第一次放行、第二次拒绝。"""
        db = _Db()
        assert LogBackedReplayGuard(db).admit("telegram", "evt-1", NOW) is True
        assert LogBackedReplayGuard(db).admit("telegram", "evt-1", NOW) is False

    def test_window_expiry_allows_again_and_prunes(self):
        db = _Db()
        guard = LogBackedReplayGuard(db, window_seconds=60.0)
        assert guard.admit("telegram", "evt-1", NOW) is True
        assert guard.admit("telegram", "evt-1", NOW + 61) is True
        rows = db.fetchall("SELECT COUNT(*) AS n FROM notification_log WHERE event_type = 'callback'")
        assert rows[0]["n"] == 1  # 过期行被清理

    def test_empty_event_id_not_admitted(self):
        db = _Db()
        assert LogBackedReplayGuard(db).admit("telegram", "", NOW) is False


class TestEndpointWiring:
    """端点接线：白名单、路由注册、支持渠道闭集。"""

    def test_whitelist_covers_callback_prefix(self):
        from docker.auth_state import AUTH_WHITELIST

        paths = [p for p, _ in AUTH_WHITELIST]
        assert "/api/notification/callback" in paths
        # 中间件按 path.startswith 匹配，故前缀覆盖 {channel} 路径参数
        assert "/api/notification/callback/telegram".startswith("/api/notification/callback")

    def test_router_registers_route(self):
        from docker.api.notification_callback import router

        paths = [route.path for route in router.routes]
        assert "/api/notification/callback/{channel}" in paths

    def test_supported_channel_closure(self):
        from docker.api.notification_callback import SUPPORTED_CALLBACK_CHANNELS

        assert set(SUPPORTED_CALLBACK_CHANNELS) == {"telegram", "dingtalk", "feishu"}

    def test_app_registers_callback_router(self):
        src = Path("docker/app.py").read_text(encoding="utf-8")
        assert "notification_callback_router" in src
