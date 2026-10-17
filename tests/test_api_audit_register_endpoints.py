"""端点级测试：审计日志读取与自助注册（体检 D-13 剩余两条路由）。

- `GET /api/admin/audit`：admin 角色校验 + 分页切片 + 上限/参数校验；
- `POST /api/auth/register`：开关关闭、限流、输入校验、用户名已存在、成功建号并下发 cookie。

两者都不打桩业务 SQL：
- 审计读取用 monkeypatch 替换 `docker.api.audit.read_audit`（只验证切片与透传）；
- 注册用 monkeypatch 替换 `docker.api.auth_register` 的用户/会话函数（验证编排与出口）。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from docker.api import audit, auth_register
from docker.auth import COOKIE_NAME, SECRET


def _admin_token(role: str = "admin") -> str:
    return jwt.encode(
        {
            "sub": "1",
            "role": role,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(audit.router)
    app.include_router(auth_register.router)
    return TestClient(app)


# ── /api/admin/audit ─────────────────────────────────────────────────


def test_audit_requires_admin(client: TestClient, monkeypatch) -> None:
    """无 Cookie ⇒ 403；拒绝路径的审计写入打桩，避免测试触碰真实库。"""
    monkeypatch.setattr("docker.auth.write_audit", lambda **kwargs: None)
    monkeypatch.setattr("docker.auth._resolve_audit_identity", lambda subject: (None, "unknown"))
    r = client.get("/api/admin/audit")
    assert r.status_code == 403
    assert r.json()["detail"] == "权限不足"


def test_audit_paginates_with_offset_and_limit(client: TestClient, monkeypatch) -> None:
    rows = [{"id": i} for i in range(1, 6)]
    calls: list[dict] = []

    def fake_read_audit(**kwargs):
        calls.append(kwargs)
        return rows

    monkeypatch.setattr(audit, "read_audit", fake_read_audit)
    client.cookies.set(COOKIE_NAME, _admin_token())

    r = client.get("/api/admin/audit", params={"limit": 2, "offset": 1, "action": "PASSWORD_CHANGE"})
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == rows[1:3]
    assert body["count"] == 2
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert body["has_more"] is True
    # 无状态分页：按 offset+limit 读，再本地切片
    assert calls == [{"user_id": None, "action": "PASSWORD_CHANGE", "limit": 3}]


def test_audit_has_more_false_at_tail(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(audit, "read_audit", lambda **kwargs: [{"id": 1}, {"id": 2}])
    client.cookies.set(COOKIE_NAME, _admin_token())
    r = client.get("/api/admin/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["has_more"] is False


@pytest.mark.parametrize("params", [{"limit": 501}, {"limit": 0}, {"offset": -1}])
def test_audit_rejects_out_of_range_params(client: TestClient, params: dict) -> None:
    client.cookies.set(COOKIE_NAME, _admin_token())
    assert client.get("/api/admin/audit", params=params).status_code == 422


# ── /api/auth/register ───────────────────────────────────────────────


@pytest.fixture()
def registration(monkeypatch):
    """把注册端点依赖的用户/会话函数全部打桩，并默认打开开关。"""
    monkeypatch.setattr(auth_register, "_ENABLE_REGISTRATION", True)
    monkeypatch.setattr(auth_register, "_registration_attempts", {})
    monkeypatch.setattr(auth_register, "write_audit", MagicMock())
    monkeypatch.setattr(auth_register, "init_users_table", lambda: None)
    monkeypatch.setattr(auth_register, "add_user", lambda *a, **k: True)
    monkeypatch.setattr(auth_register, "get_user_by_username", lambda u: {"id": 7, "username": u})
    monkeypatch.setattr(auth_register, "get_user_role", lambda u: "user")
    monkeypatch.setattr(auth_register, "_init_default_preferences", lambda uid: None)
    monkeypatch.setattr(auth_register, "_generate_token", lambda user_id, role: "tok-123")
    session_store = MagicMock()
    monkeypatch.setattr(auth_register, "get_session_store", lambda: session_store)
    return session_store


def test_register_disabled_returns_403(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(auth_register, "_ENABLE_REGISTRATION", False)
    r = client.post("/api/auth/register", data={"username": "alice", "password": "password1"})
    assert r.status_code == 403
    assert "未开放" in r.json()["detail"]


def test_register_short_username_returns_400(client: TestClient, registration) -> None:
    r = client.post("/api/auth/register", data={"username": "a", "password": "password1"})
    assert r.status_code == 400
    assert "至少2个字符" in r.json()["detail"]


def test_register_short_password_returns_400(client: TestClient, registration) -> None:
    r = client.post("/api/auth/register", data={"username": "alice", "password": "short"})
    assert r.status_code == 400
    assert "不能少于 8 位" in r.json()["detail"]


def test_register_rate_limited_after_five_attempts(client: TestClient, registration, monkeypatch) -> None:
    now = time.time()
    monkeypatch.setattr(auth_register, "_registration_attempts", {"testclient": [now - i for i in range(5)]})
    r = client.post("/api/auth/register", data={"username": "alice", "password": "password1"})
    assert r.status_code == 429


def test_register_existing_username_returns_409(client: TestClient, registration, monkeypatch) -> None:
    monkeypatch.setattr(auth_register, "add_user", lambda *a, **k: False)
    r = client.post("/api/auth/register", data={"username": "alice", "password": "password1"})
    assert r.status_code == 409
    assert "已存在" in r.json()["detail"]


def test_register_success_sets_cookies_and_session(client: TestClient, registration) -> None:
    r = client.post("/api/auth/register", data={"username": "alice", "password": "password1"})
    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "username": "alice",
        "role": "user",
        "must_change_password": False,
    }
    assert r.cookies.get(COOKIE_NAME) == "tok-123"
    assert r.cookies.get("csrf_token")
    registration.add.assert_called_once()
