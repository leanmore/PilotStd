# tests/test_health.py — /api/health 健康检查端点单元测试
"""覆盖 5 个场景：全正常 / 数据库不可用 / monitor_service 缺失 / 生产外网 403 / 生产内网 200"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from docker.api import health as health_module
from docker.app import app  # noqa: E402

_client = TestClient(app)


def test_all_services_ok():
    """所有服务正常 → 200, status: ok"""
    with (
        patch.object(health_module, "_check_database", return_value=True),
        patch.object(health_module, "_check_monitor_service", return_value=True),
        patch.object(health_module, "_check_parser", return_value=True),
    ):
        resp = _client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert all(data["services"].values())


def test_database_unavailable():
    """数据库不可用 → 200, status: degraded, database: false"""
    with (
        patch.object(health_module, "_check_database", return_value=False),
        patch.object(health_module, "_check_monitor_service", return_value=True),
        patch.object(health_module, "_check_parser", return_value=True),
    ):
        resp = _client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["services"]["database"] is False


def test_monitor_service_not_initialized():
    """monitor_service 未实例化 → 200, status: degraded, monitor_service: false"""
    with (
        patch.object(health_module, "_check_database", return_value=True),
        patch.object(health_module, "_check_monitor_service", return_value=False),
        patch.object(health_module, "_check_parser", return_value=True),
    ):
        resp = _client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["services"]["monitor_service"] is False


def test_production_external_ip_403():
    """生产环境外网 IP 访问 → 403"""
    with (
        patch.dict(os.environ, {"ENV": "production"}),
        patch.object(health_module, "_is_private_ip", return_value=False),
    ):
        resp = _client.get("/api/health")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Forbidden"


def test_production_internal_ip_allowed():
    """生产环境内网 IP 访问 → 200"""
    with (
        patch.dict(os.environ, {"ENV": "production"}),
        patch.object(health_module, "_is_private_ip", return_value=True),
        patch.object(health_module, "_check_database", return_value=True),
        patch.object(health_module, "_check_monitor_service", return_value=True),
        patch.object(health_module, "_check_parser", return_value=True),
    ):
        resp = _client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
