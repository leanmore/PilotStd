"""mark_missing 入口：挂载保护 + 幂等 + admin 端点鉴权。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from docker.api import pending as pending_api
from docker.auth import COOKIE_NAME, SECRET
from docker.session_store import get_session_store
from pilotstd.manager.pending_service import mark_missing_files


class _DB:
    """最小 DB 替身：记录 UPDATE，支持写回以验证幂等。"""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = [dict(r) for r in rows]
        self.updated: list[int] = []

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.rows]

    def execute(self, sql: str, params: tuple = ()) -> None:
        if sql.startswith("UPDATE pending_lookup SET reason"):
            row_id = params[0]
            self.updated.append(row_id)
            for r in self.rows:
                if r["id"] == row_id:
                    r["reason"] = "file_missing"


def _rows(count: int, path: str, reason: str = "pending") -> list[dict]:
    return [{"id": i + 1, "file_path": path, "reason": reason, "status": "pending"} for i in range(count)]


def test_mount_guard_skips_when_most_files_missing(tmp_path):
    """≥50 行且缺失 ≥90% ⇒ 判为挂载异常，整轮跳过，一条都不改。"""
    db = _DB(_rows(100, str(tmp_path / "not-mounted" / "a.pdf")))
    stats = mark_missing_files(db)
    assert stats["checked"] == 100
    assert stats["missing"] == 100
    assert stats["skipped"] is True
    assert stats["updated"] == 0
    assert db.updated == []


def test_small_batch_is_marked_and_idempotent(tmp_path):
    """小批量（<50 行）正常标记；第二次跑不再重复更新。"""
    missing = tmp_path / "gone.pdf"
    db = _DB(_rows(3, str(missing)))

    first = mark_missing_files(db)
    assert first["skipped"] is False
    assert first["updated"] == 3

    second = mark_missing_files(db)
    assert second["updated"] == 0          # 幂等
    assert second["missing"] == 3


def test_guard_can_be_disabled(tmp_path):
    db = _DB(_rows(100, str(tmp_path / "a.pdf")))
    stats = mark_missing_files(db, protect=False)
    assert stats["skipped"] is False
    assert stats["updated"] == 100


def _admin_cookie() -> str:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "1", "role": "admin", "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )
    get_session_store().add(token, 1, "admin")
    return token


def _user_cookie() -> str:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "2", "role": "user", "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )
    get_session_store().add(token, 2, "user")
    return token


@pytest.fixture()
def client(monkeypatch):
    """挂路由 + DB 替身（不触真实库）。"""

    class _FakeDB(_DB):
        def __init__(self) -> None:
            super().__init__(_rows(2, "/data/gone.pdf"))

    fake = _FakeDB()
    app = FastAPI()
    app.include_router(pending_api.router)
    app.dependency_overrides[pending_api.get_db] = lambda: fake
    c = TestClient(app)
    c.fake_db = fake  # type: ignore[attr-defined]
    return c


def test_endpoint_requires_admin(client):
    client.cookies.set(COOKIE_NAME, _user_cookie())
    r = client.post("/api/pending/mark-missing")
    assert r.status_code == 403


def test_endpoint_returns_stats(client):
    client.cookies.set(COOKIE_NAME, _admin_cookie())
    r = client.post("/api/pending/mark-missing")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"checked": 2, "missing": 2, "updated": 2, "skipped": False, "forced": False}


def test_endpoint_accepts_protect_false(client):
    """实测驱动（2026-11-24）：管理员确认数据真缺失时，可用 protect=false 绕过挂载保护。

    生产的挂载保护会**误报**（挂载正常、数据真缺），此前 API 无任何办法推进，
    只能手工跑脚本。现暴露 protect 参数并在响应里回 orced=true 以便审计。
    """
    client.cookies.set(COOKIE_NAME, _admin_cookie())
    r = client.post("/api/pending/mark-missing?protect=false")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["forced"] is True
    # protect=false 时即使缺口大也应真的执行更新
    assert body["updated"] == 2
