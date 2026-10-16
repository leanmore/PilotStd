"""企微回调端点层测试（T-43）：`docker/api/notification_callback.py`。

验收点（提示词明确要求）：
① wechat 从 **501 → 200**；
② GET URL 验证回**明文 echostr**（`text/plain`，不带信封）；
③ POST 解密后进入分发链路，成功应答体**恰为明文 `success`**（企微按此判定受理）；
④ **其它渠道行为不变**（telegram 仍按共享密钥头验签、未知渠道仍 501、GET 路由不串到别人）。

用 `TestClient` + 内存库，不启动真实服务、不碰真实 `data/` 配置。
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.notification_callback import router as callback_router
from pilotstd.core.notification.wechat_crypto import WeChatCrypto, compute_signature

TOKEN = "pilotstd-token"
AES_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
CORP_ID = "wwtest"
TIMESTAMP = "1700000000"
NONCE = "n1"


class _Db:
    def __init__(self) -> None:
        # TestClient 在线程池里跑端点 ⇒ 内存库必须允许跨线程使用（与 Database 的行为无关，
        # 这是测试替身自身的约束）
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            -- 与生产表列集一致（Schema 一致性门禁要求测试替身不得缺列）
            CREATE TABLE notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT, channel TEXT, title TEXT, body TEXT, standard_number TEXT,
                status TEXT, error_msg TEXT, sent_at TEXT, is_read INTEGER DEFAULT 0,
                aggregated_count INTEGER DEFAULT 1, link TEXT, icon TEXT, message_id TEXT,
                correlation_id TEXT, delivery_status TEXT, ack_status TEXT DEFAULT '',
                task_id TEXT, notify_event TEXT, content_type TEXT, task_context TEXT,
                actions TEXT, callback_data TEXT, attachments TEXT,
                channel_message_ids TEXT, task_kind TEXT,
                failed_items TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, salt TEXT,
                role TEXT, must_change_password INTEGER DEFAULT 0, created_at TEXT
            );
            """
        )
        self.conn.execute(
            "INSERT INTO notification_log (id, event_type, channel, title, body, status, sent_at, ack_status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (7, "scan_complete", "wechat", "标题", "正文", "success", "2026-10-17T00:00:00", ""),
        )
        self.conn.execute("INSERT INTO users (id, username, role) VALUES (?, ?, ?)", (1, "u", "admin"))
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


def _creds(user_id: int = 1, channel: str = "") -> dict[str, str]:
    return {"token": TOKEN, "encoding_aes_key": AES_KEY, "corpid": CORP_ID, "touser": "zhangsan"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = _Db()
    import docker.api.notification_callback as mod

    monkeypatch.setattr(mod, "_db", lambda: db)
    monkeypatch.setattr(mod, "_wechat_credentials", lambda: _creds())
    monkeypatch.setattr(mod, "_credentials_for", _creds)
    app = FastAPI()
    app.include_router(callback_router)
    return TestClient(app)


def _encrypted_body(event_key: str = "ignore:7:1", msg_id: str = "1000001") -> tuple[str, str]:
    """返回 `(encrypt, body_xml)`。"""
    plain = (
        "<xml>"
        f"<ToUserName><![CDATA[{CORP_ID}]]></ToUserName>"
        "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
        "<CreateTime>1700000000</CreateTime>"
        f"<MsgId>{msg_id}</MsgId>"
        "<MsgType><![CDATA[event]]></MsgType>"
        "<Event><![CDATA[click]]></Event>"
        f"<EventKey><![CDATA[{event_key}]]></EventKey>"
        "</xml>"
    )
    encrypt = WeChatCrypto(TOKEN, AES_KEY, CORP_ID).encrypt_message(plain)
    return encrypt, f"<xml><Encrypt><![CDATA[{encrypt}]]></Encrypt></xml>"


class TestWechatGetUrlVerification:
    def test_valid_echostr_returns_plaintext(self, client: TestClient):
        echostr = WeChatCrypto(TOKEN, AES_KEY, CORP_ID).encrypt_message("1616140317555161")
        resp = client.get(
            "/api/notification/callback/wechat",
            params={
                "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, echostr),
                "timestamp": TIMESTAMP,
                "nonce": NONCE,
                "echostr": echostr,
            },
        )
        assert resp.status_code == 200
        assert resp.text == "1616140317555161", "响应体必须是解密后的明文本身"
        assert resp.headers["content-type"].startswith("text/plain")

    def test_bad_signature_401(self, client: TestClient):
        echostr = WeChatCrypto(TOKEN, AES_KEY, CORP_ID).encrypt_message("x")
        resp = client.get(
            "/api/notification/callback/wechat",
            params={"msg_signature": "0" * 40, "timestamp": TIMESTAMP, "nonce": NONCE, "echostr": echostr},
        )
        assert resp.status_code == 401
        assert resp.text == "", "拒绝时不得回显任何内容"

    def test_illegal_base64_401(self, client: TestClient):
        resp = client.get(
            "/api/notification/callback/wechat",
            params={
                "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, "!!bad!!"),
                "timestamp": TIMESTAMP,
                "nonce": NONCE,
                "echostr": "!!bad!!",
            },
        )
        assert resp.status_code == 401


class TestWechatPostMessage:
    def test_was_501_now_200_and_plain_success(self, client: TestClient):
        """企微从 501 → 200；应答体**恰为** `success`（不是 JSON 信封）。"""
        encrypt, body = _encrypted_body()
        resp = client.post(
            "/api/notification/callback/wechat",
            params={
                "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, encrypt),
                "timestamp": TIMESTAMP,
                "nonce": NONCE,
            },
            content=body.encode("utf-8"),
        )
        assert resp.status_code == 200
        assert resp.text == "success"

    def test_decrypted_action_executed(self, client: TestClient):
        """解密 → 分发链路真的执行了动作（ack_status 落库），而不只是回 200。"""
        import docker.api.notification_callback as mod

        encrypt, body = _encrypted_body()
        client.post(
            "/api/notification/callback/wechat",
            params={
                "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, encrypt),
                "timestamp": TIMESTAMP,
                "nonce": NONCE,
            },
            content=body.encode("utf-8"),
        )
        db = mod._db()
        assert db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")["ack_status"] == "ignored"

    def test_bad_signature_401(self, client: TestClient):
        _, body = _encrypted_body()
        resp = client.post(
            "/api/notification/callback/wechat",
            params={"msg_signature": "0" * 40, "timestamp": TIMESTAMP, "nonce": NONCE},
            content=body.encode("utf-8"),
        )
        assert resp.status_code == 401

    def test_tampered_ciphertext_401(self, client: TestClient):
        encrypt, body = _encrypted_body()
        marker = "<Encrypt><![CDATA["
        idx = body.index(marker) + len(marker)
        tampered = body[:idx] + ("A" if body[idx] != "A" else "B") + body[idx + 1 :]
        resp = client.post(
            "/api/notification/callback/wechat",
            params={
                "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, encrypt),
                "timestamp": TIMESTAMP,
                "nonce": NONCE,
            },
            content=tampered.encode("utf-8"),
        )
        assert resp.status_code == 401

    def test_replay_returns_success_without_reexecuting(self, client: TestClient):
        import docker.api.notification_callback as mod

        encrypt, body = _encrypted_body()
        params = {
            "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, encrypt),
            "timestamp": TIMESTAMP,
            "nonce": NONCE,
        }
        assert client.post("/api/notification/callback/wechat", params=params, content=body.encode()).text == "success"
        db = mod._db()
        db.execute("UPDATE notification_log SET ack_status = '' WHERE id = 7")
        assert client.post("/api/notification/callback/wechat", params=params, content=body.encode()).text == "success"
        assert db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")["ack_status"] == ""


class TestOtherChannelsUnchanged:
    """其它渠道行为**不变**（本批只加 wechat 一支，不得影响既有三家与未支持渠道）。"""

    def test_telegram_missing_header_401(self, client: TestClient):
        """telegram 仍按共享密钥头验签：缺头 ⇒ 401（且响应体仍是 JSON 形状）。

        注意 token 必须是**该渠道**的日志行（`7:1` 是 wechat 行）——否则会先撞上
        "记录与渠道不匹配"的 410 降级，测不到验签这一步。
        """
        import docker.api.notification_callback as mod

        mod._db().execute(
            "INSERT INTO notification_log (id, event_type, channel, title, body, status, sent_at, ack_status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (9, "scan_complete", "telegram", "标题", "正文", "success", "2026-10-17T00:00:00", ""),
        )
        resp = client.post(
            "/api/notification/callback/telegram",
            json={"callback_query": {"id": "e1", "data": "ignore:9:1", "from": {"id": "42"}}},
        )
        assert resp.status_code == 401
        assert resp.json() == {"ok": False}, "非企微渠道的响应体仍是 JSON"

    def test_unsupported_channel_still_501(self, client: TestClient):
        resp = client.post("/api/notification/callback/unknown", json={})
        assert resp.status_code == 501
        assert resp.json() == {"ok": False}

    def test_other_channel_get_not_routed(self, client: TestClient):
        """GET 路由只挂 wechat（企微协议要求），别的渠道不得意外获得 GET 处理。"""
        resp = client.get("/api/notification/callback/telegram")
        assert resp.status_code == 405

    def test_wechat_whitelist_prefix_covers_get_route(self):
        """免鉴权白名单按前缀匹配 ⇒ 新增的 GET 路由同样在免鉴权面内（企微服务器无我方会话）。"""
        from docker.auth_state import AUTH_WHITELIST

        paths = [p for p, _ in AUTH_WHITELIST]
        assert any("/api/notification/callback/wechat".startswith(p) for p in paths)
