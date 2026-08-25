"""docker/api/settings.py 鉴权测试 — 验证 @require_role 装饰器顺序修复（SEC-001 P0 批次1）。

移除 AUTH_WHITELIST 的 /api/settings GET 后，全部 8 个接口统一走
AuthMiddleware session 认证 + require_role：无 token → 401，非 admin → 403。
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api.settings import router as settings_router
from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware
from docker.manager import get_manager_dep
from docker.session_store import get_session_store


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_settings_auth(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


def _make_token(role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


# 全部 8 个接口（GET 5 + 写 3），移除白名单后统一走 AuthMiddleware
_ALL_ENDPOINTS = [
    ("GET", "/api/settings/metadata", None),
    ("GET", "/api/settings", None),
    ("PUT", "/api/settings", {}),
    ("GET", "/api/settings/sites", None),
    ("PUT", "/api/settings/sites/test_site", {
        "max_requests": 200, "daily_limit": 800,
        "cooling_seconds": 600, "request_interval": 0.5,
    }),
    ("GET", "/api/settings/token", None),
    ("POST", "/api/settings/token/refresh", None),
    ("GET", "/api/settings/schema", None),
]

# 无副作用接口（不依赖 mgr、无写副作用）：admin 访问应 200
_ADMIN_200_ENDPOINTS = [
    ("GET", "/api/settings/metadata", None),
    ("GET", "/api/settings/token", None),
    ("GET", "/api/settings/schema", None),
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

    def test_no_token_401(self):
        """8 个接口无 token → AuthMiddleware 401（移除白名单后）。"""
        for method, path, body in _ALL_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_non_admin_403(self):
        """8 个接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in _ALL_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_admin_200(self):
        """无副作用接口 admin cookie（有效 session）→ 200。"""
        self._set_cookie("admin", with_session=True)
        self._set_csrf()
        for method, path, body in _ADMIN_200_ENDPOINTS:
            r = self.client.request(method, path)
            self.assertEqual(r.status_code, 200, f"{method} {path} admin 应 200，实际 {r.status_code}")
