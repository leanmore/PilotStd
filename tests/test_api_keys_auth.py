"""docker/api/api_keys.py 鉴权测试 — 验证 @require_role 装饰器顺序修复（SEC-001 P0 批次2）。

注意：该文件 5 个接口均已废弃（返回 410 Gone），功能已迁移至 settings 的 token 接口。
修复仅为消除错误装饰器顺序，保持 SEC-001 一致性。
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET", "test_secret_key_for_testing")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")
os.environ.setdefault("SUPERUSER", "superadmin")

from docker.api.api_keys import router as api_keys_router
from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware
from docker.session_store import get_session_store


def _make_token(role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


# 5 个废弃接口均不在白名单，走 AuthMiddleware session 认证
_ENDPOINTS = [
    ("GET", "/api/admin/api-keys"),
    ("POST", "/api/admin/api-keys"),
    ("PUT", "/api/admin/api-keys/test_key"),
    ("DELETE", "/api/admin/api-keys/test_key"),
    ("PUT", "/api/admin/api-keys/test_key/reactivate"),
]


class TestApiKeysAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(api_keys_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.client.headers.clear()

    def _set_cookie(self, role: str, with_session: bool = False):
        token = _make_token(role)
        if with_session:
            get_session_store().add(token, {"username": "test"}, ttl_seconds=3600)
        self.client.cookies.set(COOKIE_NAME, token)

    def _set_csrf(self):
        self.client.cookies.set("csrf_token", "test_csrf")
        self.client.headers["X-CSRF-Token"] = "test_csrf"

    def test_no_token_401(self):
        """5 个接口无 token → AuthMiddleware 401。"""
        for method, path in _ENDPOINTS:
            r = self.client.request(method, path)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_non_admin_403(self):
        """5 个接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path in _ENDPOINTS:
            r = self.client.request(method, path)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_admin_410_gone(self):
        """5 个接口 admin → 410 Gone（废弃接口，非 200）。"""
        self._set_cookie("admin", with_session=True)
        self._set_csrf()
        for method, path in _ENDPOINTS:
            r = self.client.request(method, path)
            self.assertEqual(r.status_code, 410, f"{method} {path} admin 应 410，实际 {r.status_code}")
