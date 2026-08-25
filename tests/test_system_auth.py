"""docker/api/system.py 鉴权测试 — SEC-001 P2 批次。

get_version：公开接口（移除 require_role），断言不含 container_id（防容器逃逸信息泄露）。
update_container / system_health / system_resources：恢复 require_role（admin only）。
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

from docker.api.system import router as system_router
from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware
from docker.manager import get_manager_dep
from docker.session_store import get_session_store


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_system_auth(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


def _make_token(role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


class TestSystemAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(system_router)
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

    # ── get_version：公开接口 ──

    def test_get_version_no_token_200(self):
        """get_version 无 token → 200（白名单），且不含 container_id。"""
        r = self.client.get("/api/system/version")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("container_id", r.json(), "get_version 不应返回 container_id")

    def test_get_version_admin_200(self):
        """get_version admin → 200，且不含 container_id。"""
        self._set_cookie("admin", with_session=True)
        r = self.client.get("/api/system/version")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("container_id", r.json(), "get_version 不应返回 container_id")

    # ── update_container / system_health / system_resources：admin only ──

    def test_admin_endpoints_no_token_401(self):
        """3 个 admin 接口无 token → AuthMiddleware 401。"""
        for method, path, body in [
            ("POST", "/api/system/update", None),
            ("GET", "/api/system/health", None),
            ("GET", "/api/system/resources", None),
        ]:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_admin_endpoints_non_admin_403(self):
        """3 个 admin 接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in [
            ("POST", "/api/system/update", None),
            ("GET", "/api/system/health", None),
            ("GET", "/api/system/resources", None),
        ]:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_admin_200(self):
        """system_resources admin → 200（require_role 放行，psutil 返回资源）。"""
        self._set_cookie("admin", with_session=True)
        r = self.client.get("/api/system/resources")
        self.assertEqual(r.status_code, 200, f"admin 访问 resources 应 200，实际 {r.status_code}")
