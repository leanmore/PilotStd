"""E3：/api/health 真实健康检查（200/207/500/403）。"""

import os
import sys
from contextlib import ExitStack
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from docker.api import health as health_module
from docker.app import app

_client = TestClient(app)

_DISK_OK = {"free_mb": 10000.0, "threshold_mb": 500.0, "ok": True}
_SCHED_OK = {"heartbeat_at": "2026-11-06T19:00:00+08:00", "age_seconds": 1.0, "ok": True}


def _patches(db=True, disk=_DISK_OK, sched=_SCHED_OK, monitor=True, parser=True):
    stack = ExitStack()
    stack.enter_context(patch.object(health_module, "_check_database_read", return_value=db))
    stack.enter_context(patch.object(health_module, "_check_database_write", return_value=db))
    stack.enter_context(patch.object(health_module, "_check_disk", return_value=disk))
    stack.enter_context(patch.object(health_module, "_check_scheduler", return_value=sched))
    stack.enter_context(patch.object(health_module, "_check_monitor_service", return_value=monitor))
    stack.enter_context(patch.object(health_module, "_check_parser", return_value=parser))
    return stack


def test_all_services_ok_200():
    with _patches():
        resp = _client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["disk"]["ok"] is True
    assert data["checks"]["database_rw"] == {"read": True, "write": True}


def test_database_unavailable_500():
    with _patches(db=False):
        resp = _client.get("/api/health")
    assert resp.status_code == 500
    data = resp.json()
    assert data["status"] == "down"
    assert data["services"]["database"] is False


def test_disk_low_207():
    with _patches(disk={"free_mb": 100.0, "threshold_mb": 500.0, "ok": False}):
        resp = _client.get("/api/health")
    assert resp.status_code == 207
    assert resp.json()["status"] == "degraded"


def test_monitor_service_flag():
    with _patches(monitor=False):
        resp = _client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["services"]["monitor_service"] is False


def test_production_external_ip_403():
    with (
        patch.dict(os.environ, {"ENV": "production"}),
        patch.object(health_module, "_is_private_ip", return_value=False),
    ):
        resp = _client.get("/api/health")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Forbidden"


def test_production_internal_ip_allowed():
    with (
        patch.dict(os.environ, {"ENV": "production"}),
        patch.object(health_module, "_is_private_ip", return_value=True),
        _patches(),
    ):
        resp = _client.get("/api/health")
    assert resp.status_code == 200
