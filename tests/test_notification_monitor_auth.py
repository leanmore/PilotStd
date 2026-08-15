"""docker/api/notification.py + monitor.py 鉴权测试 — SEC-001 P1 批次2。

notification（9 接口）：移除 @require_role（用户级模块），普通用户 200。
monitor（6 接口）：恢复 @require_role（admin 功能），非 admin 403。
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET", "test_secret_key_for_testing")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")
os.environ.setdefault("SUPERUSER", "superadmin")

from docker.api.monitor import router as monitor_router
from docker.api.notification import router as notification_router
from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware
from docker.manager import get_manager_dep
from docker.session_store import get_session_store


def _make_token(role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


# notification 9 接口（移除 require_role）
_NOTIFICATION_ENDPOINTS = [
    ("GET", "/api/notification/config", None),
    ("PUT", "/api/notification/config", {}),
    ("POST", "/api/notification/test", {}),
    ("GET", "/api/notification/logs", None),
    ("POST", "/api/notification/read", {}),
    ("GET", "/api/notification/unread-count", None),
    ("DELETE", "/api/notification/logs", None),
    ("GET", "/api/notification/policy", None),
    ("PUT", "/api/notification/policy", {"channel": "wechat"}),
]

# monitor 6 接口（恢复 require_role）
_MONITOR_ENDPOINTS = [
    ("GET", "/api/monitor/config", None),
    ("PUT", "/api/monitor/config", {}),
    ("GET", "/api/monitor/status", None),
    ("GET", "/api/monitor/stats", None),
    ("POST", "/api/monitor/start", None),
    ("POST", "/api/monitor/stop", None),
]


class TestNotificationMonitorAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(notification_router)
        app.include_router(monitor_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.client.headers.clear()
        self.client.app.dependency_overrides.clear()
        self.client.app.dependency_overrides[get_manager_dep] = lambda: MagicMock()

    def _set_cookie(self, role: str, with_session: bool = False):
        token = _make_token(role)
        if with_session:
            get_session_store().add(token, {"username": "test"}, ttl_seconds=3600)
        self.client.cookies.set(COOKIE_NAME, token)

    def _set_csrf(self):
        self.client.cookies.set("csrf_token", "test_csrf")
        self.client.headers["X-CSRF-Token"] = "test_csrf"

    # ── notification：移除 require_role ──

    def test_notification_no_token_401(self):
        """9 个接口无 token → AuthMiddleware 401。"""
        for method, path, body in _NOTIFICATION_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_notification_user_200(self):
        """普通用户 token → 200（移除 require_role，用户级模块）。"""
        mock_mgr = self.client.app.dependency_overrides[get_manager_dep]()
        mock_mgr.notification_mgr.get_unread_count.return_value = 0

        self._set_cookie("user", with_session=True)
        r = self.client.get("/api/notification/unread-count")
        self.assertEqual(r.status_code, 200, f"普通用户访问 unread-count 应 200，实际 {r.status_code}")

    # ── monitor：恢复 require_role ──

    def test_monitor_no_token_401(self):
        """6 个接口无 token → AuthMiddleware 401。"""
        for method, path, body in _MONITOR_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_monitor_non_admin_403(self):
        """6 个接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in _MONITOR_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_monitor_admin_200(self):
        """admin token → 200（require_role 放行 admin）。"""
        mock_mgr = self.client.app.dependency_overrides[get_manager_dep]()
        mock_mgr.monitor_service.get_status.return_value = {"running": False}

        self._set_cookie("admin", with_session=True)
        r = self.client.get("/api/monitor/status")
        self.assertEqual(r.status_code, 200, f"admin 访问 monitor/status 应 200，实际 {r.status_code}")
