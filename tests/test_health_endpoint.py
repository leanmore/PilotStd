"""E3：真实健康检查（磁盘/调度器心跳/数据库读写）。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api import health as health_mod
from pilotstd.core.time_utils import iso_now


class _FakeDB:
    def __init__(self, path, heartbeat=None):
        self.path = str(path)
        self._heartbeat = heartbeat
        self.executed = []

    def fetchone(self, sql, params=()):
        if "scheduler_lock" in sql:
            return {"heartbeat_at": self._heartbeat} if self._heartbeat else None
        return {"ok": 1}

    def execute(self, sql, params=()):
        self.executed.append(sql)
        return SimpleNamespace(rowcount=1)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = _FakeDB(tmp_path / "pilotstd.db", heartbeat=iso_now())
    mgr = SimpleNamespace(db=db, monitor_service=object(), parser=object())
    monkeypatch.setattr("docker.manager.get_manager", lambda: mgr)
    app = FastAPI()
    app.include_router(health_mod.router)
    return TestClient(app), db, mgr


def test_health_ok_200(client):
    c, _, _ = client
    r = c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["disk"]["threshold_mb"] == 500.0
    assert body["checks"]["scheduler"]["ok"] is True
    assert body["checks"]["database_rw"] == {"read": True, "write": True}
    assert body["timestamp"][19] in "+-" and ":" in body["timestamp"][19:]


def test_health_stale_scheduler_207(client, monkeypatch):
    c, db, _ = client
    db._heartbeat = "2020-01-01T00:00:00+08:00"
    r = c.get("/api/health")
    assert r.status_code == 207
    assert r.json()["status"] == "degraded"
    assert r.json()["checks"]["scheduler"]["ok"] is False


def test_health_database_write_down_500(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(health_mod, "_check_database_write", lambda mgr: False)
    r = c.get("/api/health")
    assert r.status_code == 500
    assert r.json()["status"] == "down"


def test_disk_threshold_degrades(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(health_mod.shutil, "disk_usage", lambda p: SimpleNamespace(free=100 * 1024 * 1024))
    r = c.get("/api/health")
    assert r.status_code == 207
    assert r.json()["checks"]["disk"]["ok"] is False
