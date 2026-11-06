"""写操作权限收口（D5-1 / D5-2）：普通用户 403、admin 放行、API Key 只读。"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware
from docker.session_store import get_session_store


def _token(role: str, user_id: int = 1) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


def _with_session(client, role: str, user_id: int = 1) -> str:
    token = _token(role, user_id)
    get_session_store().add(token, user_id, role)
    client.cookies.set("csrf_token", "csrf-test")
    return token


@pytest.fixture()
def client():
    app = FastAPI()

    @app.post("/api/validity/run")
    def _run():  # 模拟无 @require_role 的全局写端点
        return {"ok": True}

    @app.get("/api/standards/status")
    def _status():
        return {"ok": True}

    @app.post("/api/favorites")
    def _fav():
        return {"ok": True}

    @app.delete("/api/notification/logs")
    def _del():
        return {"ok": True}

    app.add_middleware(AuthMiddleware)
    return TestClient(app)


def test_user_cannot_call_global_write(client):
    client.cookies.set(COOKIE_NAME, _with_session(client, "user"))
    r = client.post("/api/validity/run", headers={"X-CSRF-Token": "csrf-test"})
    assert r.status_code == 403
    body = r.json()
    assert body["code"] == "forbidden"
    assert body["message_key"] == "auth.api.forbidden"
    assert "detail" in body


def test_admin_can_call_global_write(client):
    client.cookies.set(COOKIE_NAME, _with_session(client, "admin"))
    r = client.post("/api/validity/run", headers={"X-CSRF-Token": "csrf-test"})
    assert r.status_code == 200


def test_user_read_is_allowed(client):
    client.cookies.set(COOKIE_NAME, _with_session(client, "user"))
    assert client.get("/api/standards/status").status_code == 200


def test_user_own_data_write_is_allowed(client):
    client.cookies.set(COOKIE_NAME, _with_session(client, "user"))
    r = client.post(
        "/api/favorites", json={"record_id": 1}, headers={"X-CSRF-Token": "csrf-test"}
    )
    assert r.status_code == 200


def test_user_admin_delete_is_blocked(client):
    client.cookies.set(COOKIE_NAME, _with_session(client, "user"))
    assert client.delete("/api/notification/logs", headers={"X-CSRF-Token": "csrf-test"}).status_code == 403


def test_api_key_is_read_only(client, monkeypatch):
    monkeypatch.setattr(
        "docker.auth_middleware.verify_api_key", lambda token: {"key_id": "default"}
    )
    headers = {"X-API-KEY": "pst_whatever"}
    assert client.get("/api/standards/status", headers=headers).status_code == 200
    assert client.post("/api/validity/run", headers=headers).status_code == 403


def test_admin_write_is_audited(client, monkeypatch):
    from docker.auth import COOKIE_NAME
    from tests.test_api_write_admin_only import _with_session

    calls = []
    monkeypatch.setattr("pilotstd.core.audit.write_audit", lambda **kw: calls.append(kw))
    client.cookies.set(COOKIE_NAME, _with_session(client, "admin"))
    r = client.post("/api/validity/run", headers={"X-CSRF-Token": "csrf-test"})
    assert r.status_code == 200
    assert any(c.get("action") == "API_WRITE" and c.get("resource") == "POST /api/validity/run" for c in calls)
