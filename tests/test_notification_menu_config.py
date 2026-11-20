"""A-27：菜单配置写入口测试（PUT /api/notification/menu/config）。

鉴权沿用 A-27.3 的做法：> JWT + session store 里注册会话，cookie 走 COOKIE_NAME。
配置写入用替身（不落真实 config.json），渠道网络调用不发生。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from docker.api import notification_menu
from docker.auth import COOKIE_NAME, SECRET
from docker.session_store import get_session_store


class _FakeCfg:
    """最小配置替身：记录 set 调用，save 计数。"""

    def __init__(self) -> None:
        self.saved: dict[str, object] = {}
        self.save_count = 0

    def set(self, key: str, value: object) -> None:
        self.saved[key] = value

    def save(self) -> None:
        self.save_count += 1


def _item(i: int, children: int = 0) -> dict:
    """构造一个合法一级项（可选子项）。"""
    return {
        "id": f"m{i}",
        "label_key": f"menu.item{i}",
        "type": "group" if children else "view",
        "order": i,
        "url": f"https://example.com/{i}",
        "children": [
            {
                "id": f"m{i}c{j}",
                "label_key": f"menu.item{i}.{j}",
                "type": "view",
                "order": j,
                "url": f"https://example.com/{i}/{j}",
            }
            for j in range(1, children + 1)
        ],
    }


def _admin_cookie() -> str:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "1", "role": "admin", "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )
    get_session_store().add(token, 1, "admin")
    return token


@pytest.fixture()
def client(monkeypatch):
    """挂路由 + admin 会话 + 配置替身。"""
    fake = _FakeCfg()
    monkeypatch.setattr(notification_menu, "ConfigManager", lambda: fake)
    app = FastAPI()
    app.include_router(notification_menu.router)
    c = TestClient(app)
    c.cookies.set(COOKIE_NAME, _admin_cookie())
    c.fake_cfg = fake  # type: ignore[attr-defined]
    return c


def test_wechat_3x5_accepted_and_saved(client):
    payload = {"channel": "wechat", "enabled": True, "items": [_item(i, 5) for i in range(1, 4)]}
    r = client.put("/api/notification/menu/config", json=payload)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "channel": "wechat", "enabled": True, "items": 3}
    cfg = client.fake_cfg
    assert cfg.saved["notification.menus.wechat.enabled"] is True
    assert cfg.saved["notification.menus.wechat.last_synced"] is None
    assert cfg.save_count == 1


def test_wechat_too_many_top_level_rejected(client):
    payload = {"channel": "wechat", "enabled": True, "items": [_item(i) for i in range(1, 5)]}
    r = client.put("/api/notification/menu/config", json=payload)
    assert r.status_code == 400
    assert "too many top-level" in r.json()["detail"]


def test_unknown_channel_rejected(client):
    r = client.put("/api/notification/menu/config", json={"channel": "weibo", "enabled": True, "items": []})
    assert r.status_code == 400


def test_dingtalk_cannot_be_enabled(client):
    r = client.put("/api/notification/menu/config", json={"channel": "dingtalk", "enabled": True, "items": []})
    assert r.status_code == 400
    assert "no server-side menu" in r.json()["detail"]


def test_feishu_requires_chat_id_when_enabled(client):
    payload = {"channel": "feishu", "enabled": True, "items": [_item(1)], "chat_id": ""}
    r = client.put("/api/notification/menu/config", json=payload)
    assert r.status_code == 400
    assert "chat_id" in r.json()["detail"]


def test_feishu_with_chat_id_saved(client):
    payload = {"channel": "feishu", "enabled": True, "items": [_item(1)], "chat_id": "oc_123"}
    r = client.put("/api/notification/menu/config", json=payload)
    assert r.status_code == 200, r.text
    assert client.fake_cfg.saved["notification.menus.feishu.chat_id"] == "oc_123"


def test_disabled_empty_is_valid(client):
    r = client.put("/api/notification/menu/config", json={"channel": "telegram", "enabled": False, "items": []})
    assert r.status_code == 200
    assert client.fake_cfg.saved["notification.menus.telegram.enabled"] is False
