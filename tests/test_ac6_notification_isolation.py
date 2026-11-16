"""AC-6 集成验证：双用户通知读取/已读隔离（登录→触发→通知→未读/已读→互不可见）。

不碰生产：临时 SQLite 跑迁移链，真实 NotificationManager 落库，真实
`/api/notification/logs`、`/api/notification/read`、`/api/notification/unread-count`
路由 + JWT 会话；断言 user2 看不到/改不到 user1 的通知。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api.notification_logs import router as notification_logs_router
from docker.auth import COOKIE_NAME, CSRF_HEADER, SECRET, AuthMiddleware
from docker.manager import get_manager_dep
from docker.session_store import get_session_store
from pilotstd.core.db import Database
from pilotstd.core.notification.context import NotificationContext
from pilotstd.core.notification.manager import NotificationManager

CSRF = "csrf-ac6-test"


class _Cfg:
    def __init__(self, path: str):
        self._filepath = path
        self._data: dict[str, object] = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


class _Policy:
    def get_channels_for_event(self, user_id, event_type, event_data):
        return ["web"]


class _Channel:
    name = "web"

    def send(self, msg):
        return True


def _token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture()
def client(tmp_path):
    db = Database(str(tmp_path / "ac6.db"))
    for uid, role in ((1, "admin"), (2, "user")):
        db.execute(
            "INSERT INTO users (id, username, password_hash, salt, role) VALUES (?,?,?,?,?)",
            (uid, f"u{uid}", "h", "s", role),
        )
    cfg = _Cfg(str(tmp_path / "config.json"))
    nmgr = NotificationManager(cfg, db, user_id=1)
    nmgr._enabled = True
    nmgr._policy = _Policy()
    nmgr._channels = {"web": _Channel()}
    nmgr.send_event(
        "archive_complete",
        {"count": 1},
        bypass_aggregation=True,
        context=NotificationContext(scope="admin", user_id=1),
    )
    nmgr2 = NotificationManager(cfg, db, user_id=2)
    nmgr2._enabled = True
    nmgr2._policy = _Policy()
    nmgr2._channels = {"web": _Channel()}
    nmgr2.send_event(
        "archive_complete",
        {"count": 2},
        bypass_aggregation=True,
        context=NotificationContext(scope="admin", user_id=2),
    )

    def _get_user(uid: int):
        row = db.fetchone("SELECT id FROM users WHERE id=?", (uid,))
        return SimpleNamespace(id=uid) if row else None

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(notification_logs_router)
    fake_mgr = SimpleNamespace(
        notification_mgr=nmgr,
        user_service=SimpleNamespace(get_user_by_id=_get_user),
    )
    app.dependency_overrides[get_manager_dep] = lambda: fake_mgr
    tc = TestClient(app)

    tokens = {1: _token(1, "admin"), 2: _token(2, "user")}
    for uid, token in tokens.items():
        get_session_store().add(token, uid, "admin" if uid == 1 else "user")
    yield tc, db, tokens
    db.close()


def _auth(tc: TestClient, tokens: dict[int, str], uid: int) -> None:
    tc.cookies.clear()
    tc.cookies.set(COOKIE_NAME, tokens[uid])
    tc.cookies.set("csrf_token", CSRF)


def _log_ids(tc: TestClient, tokens: dict[int, str], uid: int) -> list[int]:
    _auth(tc, tokens, uid)
    r = tc.get("/api/notification/logs")
    assert r.status_code == 200, r.text
    return [item["id"] for item in r.json()["items"]]


def test_user_sees_only_own_notifications(client):
    tc, _db, tokens = client
    user1_ids = _log_ids(tc, tokens, 1)
    user2_ids = _log_ids(tc, tokens, 2)
    assert user1_ids and user2_ids
    assert not set(user1_ids) & set(user2_ids), (user1_ids, user2_ids)


def test_read_by_user1_does_not_affect_user2(client):
    tc, _db, tokens = client
    user1_ids = _log_ids(tc, tokens, 1)
    _auth(tc, tokens, 2)
    before = tc.get("/api/notification/unread-count").json()["count"]

    _auth(tc, tokens, 1)
    r = tc.post("/api/notification/read", json={"id": user1_ids[0]}, headers={CSRF_HEADER: CSRF})
    assert r.status_code == 200, r.text

    _auth(tc, tokens, 2)
    after = tc.get("/api/notification/unread-count").json()["count"]
    assert after == before, (before, after)


def test_user2_cannot_read_user1_notification(client):
    tc, _db, tokens = client
    user1_ids = _log_ids(tc, tokens, 1)
    _auth(tc, tokens, 2)
    r = tc.post("/api/notification/read", json={"id": user1_ids[0]}, headers={CSRF_HEADER: CSRF})
    assert r.status_code in (403, 404), r.text
