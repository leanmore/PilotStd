"""POST /api/admin/monitor/catchup 鉴权与触发结果契约。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.monitor import router
from tests._auth_helpers import admin_cookies


def test_trigger_catchup_returns_started():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, cookies=admin_cookies())
    fake = SimpleNamespace(trigger_catchup=lambda: {"started": True, "reason": ""})
    with patch("docker.api.monitor.get_scheduler", return_value=fake):
        r = client.post("/api/admin/monitor/catchup")
    assert r.status_code == 200
    assert r.json() == {"started": True, "reason": ""}


def test_trigger_catchup_passes_reason():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, cookies=admin_cookies())
    fake = SimpleNamespace(trigger_catchup=lambda: {"started": False, "reason": "catchup already running"})
    with patch("docker.api.monitor.get_scheduler", return_value=fake):
        r = client.post("/api/admin/monitor/catchup")
    assert r.status_code == 200
    assert r.json()["started"] is False
    assert r.json()["reason"] == "catchup already running"
