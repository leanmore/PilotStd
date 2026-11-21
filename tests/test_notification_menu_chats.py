"""A-27 飞书 chat_id 发现：客户端 + 端点的测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from docker.api import notification_menu
from docker.auth import COOKIE_NAME, SECRET
from docker.session_store import get_session_store
from pilotstd.core.notification.menu.clients import FeishuMenuClient


class _Transport:
    """假传输：token 与群列表两步都返回固定结构。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, url, payload=None, headers=None):
        self.calls.append((method, url))
        if "tenant_access_token" in url:
            return {"code": 0, "tenant_access_token": "t-fake"}
        return {
            "code": 0,
            "data": {"items": [{"chat_id": "oc_1", "name": "标准群"}, {"chat_id": "oc_2"}]},
        }


def test_feishu_client_lists_chats():
    tr = _Transport()
    client = FeishuMenuClient("app", "secret", "oc_x", transport=tr)
    chats = client.list_chats()
    assert chats == [{"chat_id": "oc_1", "name": "标准群"}, {"chat_id": "oc_2", "name": ""}]
    assert any("im/v1/chats" in url for _, url in tr.calls)


def test_feishu_client_without_credentials_returns_empty():
    client = FeishuMenuClient("", "", "", transport=_Transport())
    assert client.list_chats() == []


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
    """路由 + admin 会话 + 假客户端（不访问真实飞书）。"""

    class _Fake:
        def supports_menu(self):
            return True

        def list_chats(self):
            return [{"chat_id": "oc_9", "name": "测试群"}]

    monkeypatch.setattr(notification_menu, "ConfigManager", lambda: object())
    monkeypatch.setattr(notification_menu, "build_client", lambda ch, cfg: _Fake())
    app = FastAPI()
    app.include_router(notification_menu.router)
    c = TestClient(app)
    c.cookies.set(COOKIE_NAME, _admin_cookie())
    return c


def test_chats_endpoint_returns_list(client):
    r = client.get("/api/notification/menu/chats", params={"channel": "feishu"})
    assert r.status_code == 200, r.text
    assert r.json() == {"channel": "feishu", "chats": [{"chat_id": "oc_9", "name": "测试群"}]}


def test_chats_endpoint_rejects_non_feishu(client):
    r = client.get("/api/notification/menu/chats", params={"channel": "wechat"})
    assert r.status_code == 400
    assert "only feishu" in r.json()["detail"]


def test_chats_endpoint_rejects_unknown_channel(client):
    r = client.get("/api/notification/menu/chats", params={"channel": "weibo"})
    assert r.status_code == 400
