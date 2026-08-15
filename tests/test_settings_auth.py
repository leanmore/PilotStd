"""docker/api/settings.py 鉴权测试 — 验证 @require_role 装饰器顺序修复（SEC-001 P0 批次1）。

区分白名单 GET（AuthMiddleware 放行 → require_role 403）与非白名单写操作
（AuthMiddleware session 认证 → require_role 403）两种链路。
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

from docker.api.settings import router as settings_router
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


# GET 接口在 AUTH_WHITELIST（/api/settings 前缀 + GET），AuthMiddleware 放行
_GET_ENDPOINTS = [
    "/api/settings/metadata",
    "/api/settings",
    "/api/settings/sites",
    "/api/settings/token",
    "/api/settings/schema",
]

# 写操作不在白名单，走 AuthMiddleware session 认证 + require_role
_WRITE_ENDPOINTS = [
    ("PUT", "/api/settings", {}),
    ("PUT", "/api/settings/sites/test_site", {
        "max_requests": 200, "daily_limit": 800,
        "cooling_seconds": 600, "request_interval": 0.5,
    }),
    ("POST", "/api/settings/token/refresh", None),
]

# 无副作用 GET 接口：admin 访问应 200
_ADMIN_200_ENDPOINTS = [
    "/api/settings/metadata",
    "/api/settings/token",
    "/api/settings/schema",
]


class TestSettingsAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(settings_router)
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

    def test_get_endpoints_no_token_403(self):
        """GET 白名单接口无 token → require_role 403。"""
        for path in _GET_ENDPOINTS:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 403, f"GET {path} 无 token 应 403，实际 {r.status_code}")

    def test_get_endpoints_non_admin_403(self):
        """GET 白名单接口非 admin cookie → require_role 403。"""
        self._set_cookie("user")
        for path in _GET_ENDPOINTS:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 403, f"GET {path} 非 admin 应 403，实际 {r.status_code}")

    def test_write_endpoints_no_token_401(self):
        """写接口无 token → AuthMiddleware 401。"""
        for method, path, body in _WRITE_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_write_endpoints_non_admin_403(self):
        """写接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in _WRITE_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_admin_cookie_200(self):
        """无副作用 GET 接口 admin cookie → 200（require_role 放行 admin）。"""
        self._set_cookie("admin")
        for path in _ADMIN_200_ENDPOINTS:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, f"GET {path} admin 应 200，实际 {r.status_code}")
