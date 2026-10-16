"""企微回调入站的服务层测试（T-43）：密文 XML → 解密 → 验签 → 分发链路。

覆盖提示词要求的四类拒绝（签名错 / 篡改 1 字节 / receiveid 不匹配 / echostr 非法 base64）
与**成功路径**（解密后进入与另外三家**同一**分发出口：幂等 + 服务端角色授权 + 执行动作）。
"""

from __future__ import annotations

import base64
import sqlite3

from pilotstd.core.notification.callback_service import handle_callback, verify_wechat_url
from pilotstd.core.notification.wechat_crypto import WeChatCrypto, compute_signature

TOKEN = "pilotstd-token"
AES_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
CORP_ID = "wwtest"
TIMESTAMP = "1700000000"
NONCE = "n1"
NOW = 1_700_000_000.0


class _Db:
    """内存库（接口与 `Database` 同款：fetchall/fetchone/execute，行可按下标取）。"""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
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

    def seed(self, log_id: int = 7, user_id: int = 1, role: str = "admin") -> None:
        self.execute(
            "INSERT INTO notification_log (id, event_type, channel, title, body, status, sent_at, ack_status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (log_id, "scan_complete", "wechat", "标题", "正文", "success", "2026-10-17T00:00:00", ""),
        )
        self.execute("INSERT OR REPLACE INTO users (id, username, role) VALUES (?, ?, ?)", (user_id, "u", role))


def _creds(user_id: int = 1, channel: str = "wechat") -> dict[str, str]:
    """企微**企业级**凭据（`token`/`encoding_aes_key` 参与验签解密，`corpid` 是 receiveid）。"""
    return {"token": TOKEN, "encoding_aes_key": AES_KEY, "corpid": CORP_ID, "touser": "zhangsan"}


def _crypto(receive_id: str = CORP_ID) -> WeChatCrypto:
    return WeChatCrypto(TOKEN, AES_KEY, receive_id)


def _encrypted_request(
    event_key: str = "ignore:7:1",
    from_user: str = "zhangsan",
    msg_id: str = "1000001",
    receive_id: str = CORP_ID,
    token: str = TOKEN,
) -> tuple[dict[str, str], bytes]:
    """构造一次真实的企微消息回调（密文 XML + 查询串签名）。"""
    plain = (
        "<xml>"
        f"<ToUserName><![CDATA[{receive_id}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        "<CreateTime>1700000000</CreateTime>"
        f"<MsgId>{msg_id}</MsgId>"
        "<MsgType><![CDATA[event]]></MsgType>"
        "<Event><![CDATA[click]]></Event>"
        f"<EventKey><![CDATA[{event_key}]]></EventKey>"
        "</xml>"
    )
    encrypt = _crypto(receive_id).encrypt_message(plain)
    body = f"<xml><Encrypt><![CDATA[{encrypt}]]></Encrypt></xml>".encode("utf-8")
    headers = {
        "msg_signature": compute_signature(token, TIMESTAMP, NONCE, encrypt),
        "timestamp": TIMESTAMP,
        "nonce": NONCE,
    }
    return headers, body


def _handle(db, headers, body, creds=None, now=NOW):
    effective = _creds() if creds is None else creds
    return handle_callback(db, "wechat", headers, body, _creds, now=now, credentials=effective)


class TestWechatHappyPath:
    def test_decrypted_event_enters_dispatch_chain(self):
        """解密后进入**既有分发链路**：管理员 ignore ⇒ 200 且 ack_status 落库。"""
        db = _Db()
        db.seed()
        headers, body = _encrypted_request()
        outcome = _handle(db, headers, body)
        assert outcome.status == 200, outcome.reason_key
        assert outcome.payload["ok"] is True
        assert db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")["ack_status"] == "ignored"

    def test_replayed_event_is_idempotent(self):
        """同一 `MsgId` 重投 ⇒ 200 但动作不重复执行（企微会重投）。"""
        db = _Db()
        db.seed()
        headers, body = _encrypted_request()
        assert _handle(db, headers, body).status == 200
        db.execute("UPDATE notification_log SET ack_status = '' WHERE id = 7")
        second = _handle(db, headers, body)
        assert second.status == 200
        assert second.reason_key == "notification.callback.replayed"
        assert db.fetchone("SELECT ack_status FROM notification_log WHERE id = 7")["ack_status"] == ""

    def test_non_admin_forbidden(self):
        """身份来自通道侧（FromUserName）+ DB 角色；非管理员 403（不信任载荷）。"""
        db = _Db()
        db.seed(role="user")
        headers, body = _encrypted_request()
        assert _handle(db, headers, body).status == 403

    def test_unknown_action_forbidden(self):
        db = _Db()
        db.seed()
        headers, body = _encrypted_request(event_key="drop_database:7:1")
        assert _handle(db, headers, body).status == 403


class TestWechatRejections:
    def test_bad_signature_rejected(self):
        db = _Db()
        db.seed()
        headers, body = _encrypted_request()
        headers["msg_signature"] = "0" * 40
        assert _handle(db, headers, body).status == 401

    def test_tampered_ciphertext_rejected(self):
        """密文被篡改 1 字节 ⇒ 401（且不得抛未捕获异常）。"""
        db = _Db()
        db.seed()
        headers, body = _encrypted_request()
        marker = b"<Encrypt><![CDATA["
        start = body.index(marker) + len(marker)
        tampered = body[:start] + bytes([body[start] ^ 0x01]) + body[start + 1 :]
        assert _handle(db, headers, tampered).status == 401

    def test_receive_id_mismatch_rejected(self):
        """密文里的 ToUserName（corpid）与配置不符 ⇒ 401。"""
        db = _Db()
        db.seed()
        headers, body = _encrypted_request(receive_id="ww-other-corp")
        assert _handle(db, headers, body).status == 401

    def test_illegal_base64_echostr_rejected_without_exception(self):
        """`echostr` 非法 base64 ⇒ 拒绝且不抛未捕获异常（URL 验证路径）。"""
        headers = {"msg_signature": "x", "timestamp": TIMESTAMP, "nonce": NONCE}
        assert verify_wechat_url(headers, "!!not-base64!!", credentials=_creds()) == ""

    def test_missing_credentials_rejected(self):
        db = _Db()
        db.seed()
        headers, body = _encrypted_request()
        assert _handle(db, headers, body, creds={}).status == 401

    def test_unknown_actor_without_fallback_rejected(self):
        """多用户场景下 FromUserName 匹配不到人 ⇒ 401（单用户才回退到唯一用户）。"""
        db = _Db()
        db.seed(user_id=1)
        db.execute("INSERT OR REPLACE INTO users (id, username, role) VALUES (?, ?, ?)", (2, "u2", "admin"))

        def creds_for(user_id: int, channel: str = "") -> dict[str, str]:
            if user_id == 1:
                return _creds()
            other = dict(_creds())
            other["touser"] = "lisi"
            return other

        headers, body = _encrypted_request(from_user="wangwu")
        outcome = handle_callback(db, "wechat", headers, body, creds_for, now=NOW, credentials=_creds())
        assert outcome.status == 401

    def test_json_body_rejected(self):
        """非 XML 体质（例如误配成 JSON 的渠道）⇒ 401，不炸。"""
        db = _Db()
        db.seed()
        outcome = handle_callback(
            db,
            "wechat",
            {"msg_signature": "x", "timestamp": TIMESTAMP, "nonce": NONCE},
            b'{"action": "ignore"}',
            _creds,
            now=NOW,
            credentials=_creds(),
        )
        assert outcome.status == 401

    def test_missing_nonce_rejected(self):
        db = _Db()
        db.seed()
        headers, body = _encrypted_request()
        del headers["nonce"]
        assert _handle(db, headers, body).status == 401


class TestWechatUrlVerification:
    """GET URL 验证：验签 → 解密 echostr → 返回明文（响应体本体）。"""

    def test_verify_url_returns_plaintext(self):
        echostr = _crypto().encrypt_message("1616140317555161")
        headers = {
            "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, echostr),
            "timestamp": TIMESTAMP,
            "nonce": NONCE,
        }
        assert verify_wechat_url(headers, echostr, credentials=_creds()) == "1616140317555161"

    def test_verify_url_bad_signature_returns_empty(self):
        echostr = _crypto().encrypt_message("x")
        headers = {"msg_signature": "0" * 40, "timestamp": TIMESTAMP, "nonce": NONCE}
        assert verify_wechat_url(headers, echostr, credentials=_creds()) == ""

    def test_verify_url_reads_credentials_via_callback(self):
        """也可经 `credentials_for` 取凭据（端点之外的调用方形态）。"""
        echostr = _crypto().encrypt_message("hello")
        headers = {
            "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, echostr),
            "timestamp": TIMESTAMP,
            "nonce": NONCE,
        }
        plain = verify_wechat_url(headers, echostr, credentials_for=_creds, user_id=1)
        assert plain == "hello"

    def test_verify_url_illegal_base64_returns_empty(self):
        headers = {
            "msg_signature": compute_signature(TOKEN, TIMESTAMP, NONCE, "QUJDRA=="),
            "timestamp": TIMESTAMP,
            "nonce": NONCE,
        }
        assert verify_wechat_url(headers, base64.b64encode(b"xx").decode(), credentials=_creds()) == ""
