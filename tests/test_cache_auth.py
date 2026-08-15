"""docker/api/cache.py 鉴权测试 — 验证 @require_role 装饰器顺序修复（SEC-001 P0 批次3）。

4 个接口均不在白名单，走 AuthMiddleware session 认证 + require_role。
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET", "test_secret_key_for_testing")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")
os.environ.setdefault("SUPERUSER", "superadmin")

from docker.api.cache import router as cache_router
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


# (method, path, body)
_ENDPOINTS = [
    ("GET", "/api/cache/config", None),
    ("PUT", "/api/cache/config", {}),
    ("GET", "/api/cache/stats", None),
    ("POST", "/api/cache/cleanup", None),
]


class TestCacheAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(cache_router)
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
        """4 个接口无 token → AuthMiddleware 401。"""
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_non_admin_403(self):
        """4 个接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    @patch("docker.api.cache.CacheManager")
    def test_admin_200(self, mock_cm_cls):
        """4 个接口 admin → 200（require_role 放行 admin）。"""
        mock_cm = mock_cm_cls.return_value
        mock_cm.get_config.return_value = {"max_size_mb": 100, "auto_cleanup": True, "cleanup_ratio": 0.8}
        mock_cm.get_stats.return_value = {"size_mb": 0, "file_count": 0}
        mock_cm.set_config.return_value = None
        mock_cm.cleanup.return_value = None

        self._set_cookie("admin", with_session=True)
        self._set_csrf()
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 200, f"{method} {path} admin 应 200，实际 {r.status_code}")
