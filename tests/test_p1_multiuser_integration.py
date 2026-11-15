"""P1 集成验证：真实 NotificationManager + 临时库 + 真实路由，验证事件归属 user_id。

不碰生产：临时 DB 跑迁移链，两个管理员会话分别触发 /api/auto 与 /api/archive，
断言 notification_log 的 user_id 分别是 1、2，且没有 user_id=0。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api.archive import router as archive_router
from docker.api.auto import router as auto_router
from docker.auth import COOKIE_NAME, CSRF_HEADER, SECRET, AuthMiddleware
from docker.manager import get_manager_dep
from docker.session_store import get_session_store
from pilotstd.core.db import Database
from pilotstd.core.notification.manager import NotificationManager

CSRF = "csrf-p1-test"


class _Cfg:
    def __init__(self, path: str):
        self._filepath = path
        self._data: dict[str, str] = {}

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


class _Store:
    def update_step(self, *args, **kwargs):
        return None


class _Manager:
    """最小 manager：把端点传入的 context 交给真实 NotificationManager 落库。"""

    def __init__(self, config, mgr1: NotificationManager, mgr2: NotificationManager):
        self.cfg = {"storage.root_dir": "", "storage.inbox_dir": "/inbox"}
        self.pipeline_store = _Store()
        self._by_user = {1: mgr1, 2: mgr2}

    def auto_run(self, root_path, _adapter=None, context=None):
        self._by_user[context.user_id].send_event(
            "scan_complete", {"count": 1}, bypass_aggregation=True, context=context
        )
        return {"scan": 1}

    def archive_standards(self, parsed_list, word_source_root="", context=None):
        self._by_user[context.user_id].send_event(
            "archive_complete", {"count": len(parsed_list)}, bypass_aggregation=True, context=context
        )
        return {"moved": 0, "failed": 0, "details": []}


def _token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "role": "admin", "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "p1.db"))
    for uid in (1, 2):
        db.execute(
            "INSERT INTO users (id, username, password_hash, salt, role) VALUES (?,?,?,?,?)",
            (uid, f"u{uid}", "h", "s", "admin"),
        )
    managers = {}
    for uid in (1, 2):
        cfg = _Cfg(str(tmp_path / "config.json"))
        m = NotificationManager(cfg, db, user_id=uid)
        m._enabled = True
        m._policy = _Policy()
        m._channels = {"web": _Channel()}
        m._local_sink = None
        managers[uid] = m

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(auto_router)
    app.include_router(archive_router)
    mgr = _Manager({}, managers[1], managers[2])
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    tc = TestClient(app)

    for uid in (1, 2):
        token = _token(uid)
        get_session_store().add(token, uid, "admin")
        tc.cookies.set(COOKIE_NAME, token)
        tc.cookies.set("csrf_token", CSRF)
        # TestClient 共用 cookie；每个用例内先清空再按需设置
    yield tc, db
    db.close()


def _auth(tc: TestClient, uid: int) -> None:
    tc.cookies.clear()
    token = _token(uid)
    get_session_store().add(token, uid, "admin")
    tc.cookies.set(COOKIE_NAME, token)
    tc.cookies.set("csrf_token", CSRF)


def _rows(db: Database, event_type: str):
    return [dict(r) for r in db.fetchall(
        "SELECT user_id, event_type FROM notification_log WHERE event_type=? ORDER BY id", (event_type,)
    )]


def test_auto_attributes_to_triggering_admin(client):
    tc, db = client
    _auth(tc, 1)
    r = tc.post("/api/auto", headers={CSRF_HEADER: CSRF})
    assert r.status_code == 200, r.text
    assert [row["user_id"] for row in _rows(db, "scan_complete")] == [1]


def test_archive_attributes_to_second_admin(client):
    tc, db = client
    _auth(tc, 2)
    payload = {"items": [{"source_path": "", "logical_code": "GB", "number": 1, "year": 2020}], "run_id": "r1"}
    r = tc.post("/api/archive", json=payload, headers={CSRF_HEADER: CSRF})
    assert r.status_code == 200, r.text
    assert [row["user_id"] for row in _rows(db, "archive_complete")] == [2]


def test_no_system_zero_rows(client):
    tc, db = client
    _auth(tc, 1)
    tc.post("/api/auto", headers={CSRF_HEADER: CSRF})
    _auth(tc, 2)
    payload = {"items": [{"source_path": "", "logical_code": "GB", "number": 1, "year": 2020}], "run_id": "r2"}
    tc.post("/api/archive", json=payload, headers={CSRF_HEADER: CSRF})
    zeros = db.fetchone("SELECT COUNT(*) AS c FROM notification_log WHERE user_id=0")["c"]
    assert zeros == 0
