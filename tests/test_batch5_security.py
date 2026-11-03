"""批次五：配置密钥加密补全 + 鉴权三处收口。"""

import json

from pilotstd.core.config.crypto import (
    _is_sensitive,
    _walk_sensitive,
    has_plaintext_sensitive,
)

MEASURED_KEYS = [
    "ocr.baidu_api_key",
    "ocr.baidu_secret_key",
    "notification.channels.telegram.bot_token",
    "notification.channels.dingtalk.app_secret",
    "notification.channels.wechat.webhook_url",
    "wechat_ip.encrypt_secret",
]


def test_measured_keys_are_sensitive():
    for key in MEASURED_KEYS:
        assert _is_sensitive(key), key
    # 非敏感键不得被误伤
    for key in ("notification.web_base_url", "notification.channels.telegram.chat_id", "storage.root_dir"):
        assert not _is_sensitive(key), key


def test_walk_sensitive_encrypts_measured_keys():
    class FakeFernet:
        def encrypt(self, b):
            return b"gAAAAA-cipher"

        def decrypt(self, b):
            return b"plain"

    data = {
        "ocr": {"baidu_api_key": "ak", "baidu_secret_key": "sk"},
        "notification": {"channels": {"telegram": {"bot_token": "1:ABC"}}},
        "wechat_ip": {"encrypt_secret": "s3"},
    }
    out = _walk_sensitive(data, encrypt=True, fernet=FakeFernet())
    assert out["ocr"]["baidu_api_key"] == "gAAAAA-cipher"
    assert out["ocr"]["baidu_secret_key"] == "gAAAAA-cipher"
    assert out["notification"]["channels"]["telegram"]["bot_token"] == "gAAAAA-cipher"
    assert out["wechat_ip"]["encrypt_secret"] == "gAAAAA-cipher"


def test_has_plaintext_sensitive_detects_and_clears():
    assert has_plaintext_sensitive({"ocr": {"baidu_api_key": "ak"}})
    assert not has_plaintext_sensitive({"ocr": {"baidu_api_key": "gAAAAAxx"}})
    assert not has_plaintext_sensitive({"ocr": {"baidu_api_key": ""}})
    assert not has_plaintext_sensitive({"storage": {"root_dir": "/standards"}})


def test_config_manager_self_heals_plaintext_on_load(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"ocr": {"baidu_api_key": "plain-ak"}, "notification": {"enabled": False}}),
        encoding="utf-8",
    )

    from pilotstd.core.config import ConfigManager

    cfg = ConfigManager(str(path))

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["ocr"]["baidu_api_key"].startswith("gAAAAA"), "明文密钥必须被写回为密文"
    assert not has_plaintext_sensitive(raw)
    # 内存中仍是明文（加解密只发生在磁盘边界）
    assert cfg.get("ocr.baidu_api_key") == "plain-ak"


def test_verify_api_key_returns_key_id_only(tmp_path, monkeypatch):
    from pilotstd.core.config import get_db_path as real_get_db_path
    from pilotstd.core.db import Database

    db_path = str(tmp_path / "k.db")
    Database(db_path).close()
    monkeypatch.setattr("pilotstd.core.config.get_db_path", lambda: db_path)
    assert real_get_db_path  # 保留引用，避免误删导入

    import hashlib

    from pilotstd.core.db import Database as DB

    db = DB(db_path)
    db.execute(
        "INSERT INTO api_keys (key_id, key_hash, scopes, is_active) VALUES ('pst_static', ?, '[\"query:read\"]', 1)",
        (hashlib.sha256(b"abc").hexdigest(),),
    )

    from docker.auth_state import verify_api_key

    info = verify_api_key("pst_abc")
    assert info == {"key_id": "pst_static"}
    assert verify_api_key("pst_wrong") is None


def test_logs_removed_from_whitelist():
    from docker.auth_state import AUTH_WHITELIST

    prefixes = [p for p, _ in AUTH_WHITELIST]
    assert "/api/logs" not in prefixes


def test_query_debug_requires_admin(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import docker.api.query_debug as qd

    monkeypatch.setattr("docker.auth.write_audit", lambda **kwargs: None)

    app = FastAPI()
    app.include_router(qd.router)
    client = TestClient(app)

    resp = client.post("/api/query/debug", json={"query": "GB/T 1"})
    assert resp.status_code == 403
