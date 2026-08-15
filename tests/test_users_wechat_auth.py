"""docker/api/users.py + wechat_ip.py 鉴权测试 — SEC-001 遗漏接口补测。

AST 脚本 check_decorator_order.py 发现的遗漏：users.py 4 处 + wechat_ip.py 4 处
均为 admin 功能（用户管理/企业微信 IP），恢复 require_role。
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

from docker.api.users import router as users_router
from docker.api.wechat_ip import router as wechat_ip_router
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


# users 4 + wechat_ip 4
_ENDPOINTS = [
    ("GET", "/api/users", None),
    ("POST", "/api/users", {"username": "testuser", "password": "testpass123", "role": "user"}),
    ("DELETE", "/api/users/99", None),
    ("PUT", "/api/users/password", {"old_password": "old", "new_password": "newpass"}),
    ("GET", "/api/wechat-ip/config", None),
    ("PUT", "/api/wechat-ip/config", {}),
    ("POST", "/api/wechat-ip/check", None),
    ("GET", "/api/wechat-ip/status", None),
]


class TestUsersWechatAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(users_router)
        app.include_router(wechat_ip_router)
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
        """8 个接口无 token → AuthMiddleware 401。"""
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_non_admin_403(self):
        """8 个接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_admin_200(self):
        """wechat_ip/status admin → 200（require_role 放行）。"""
        mock_mgr = self.client.app.dependency_overrides[get_manager_dep]()
        mock_mgr.wechat_ip_service.get_status.return_value = {"ok": True}

        self._set_cookie("admin", with_session=True)
        r = self.client.get("/api/wechat-ip/status")
        self.assertEqual(r.status_code, 200, f"admin 访问 wechat-ip/status 应 200，实际 {r.status_code}")
