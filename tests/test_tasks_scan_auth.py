"""docker/api/tasks.py + scan.py 鉴权测试 — SEC-001 P1 批次1。

9 个接口（tasks 7 + scan 2）均在非白名单，走 AuthMiddleware session 认证 + require_role。
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

from docker.api.scan import router as scan_router
from docker.api.tasks import router as tasks_router


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_tasks_scan_auth(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass
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


# (method, path, body) — 9 个接口
_ENDPOINTS = [
    ("GET", "/api/tasks", None),
    ("GET", "/api/tasks/runs", None),
    ("GET", "/api/tasks/test_id", None),
    ("POST", "/api/tasks", {}),
    ("POST", "/api/tasks/test_id/retry", None),
    ("POST", "/api/tasks/test_id/cancel", None),
    ("GET", "/api/tasks/runs/test_run", None),
    ("POST", "/api/scan", {}),
    ("POST", "/api/scan-and-index", None),
]

# 无副作用读接口：admin 访问应 200
_ADMIN_200_ENDPOINTS = [
    ("GET", "/api/tasks", None),
    ("GET", "/api/tasks/runs", None),
]


class TestTasksScanAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(tasks_router)
        app.include_router(scan_router)
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
        """9 个接口无 token → AuthMiddleware 401。"""
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_non_admin_403(self):
        """9 个接口非 admin（有效 session + CSRF）→ require_role 403。"""
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_admin_200(self):
        """无副作用读接口 admin → 200。"""
        mock_mgr = self.client.app.dependency_overrides[get_manager_dep]()
        mock_mgr.task_queue.get_all.return_value = []
        mock_mgr.db.fetchone.return_value = {"cnt": 0}
        mock_mgr.db.fetchall.return_value = []

        self._set_cookie("admin", with_session=True)
        self._set_csrf()
        for method, path, body in _ADMIN_200_ENDPOINTS:
            r = self.client.request(method, path)
            self.assertEqual(r.status_code, 200, f"{method} {path} admin 应 200，实际 {r.status_code}")
