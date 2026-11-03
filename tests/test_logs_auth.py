"""docker/api/logs.py 鉴权测试 — 验证 @require_role 装饰器顺序修复 + 白名单收口。

背景：
1. logs.py 原将 @require_role 写在 @router.get 外层，导致 FastAPI 注册的是未包裹的
   原函数，require_role 鉴权失效；修复后 @require_role 内层生效，需 request: Request 读 cookie。
2. 2026-11-03：`/api/logs` 从 AuthMiddleware 白名单移除（原放行等于跳过会话撤销/CSRF/限流），
   现在无会话直接 401，有会话但非 admin 才由 require_role 返回 403。
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api.logs import router as logs_router
from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware
from docker.session_store import get_session_store


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_logs_auth(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


def _make_token(role: str) -> str:
    """构造指定角色的 JWT（与 auth.py _generate_token 同构）。"""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


def _with_session(role: str) -> str:
    """签发 token 并写入服务端会话（中间件会校验会话是否存在）。"""
    token = _make_token(role)
    get_session_store().add(token, 1, role)
    return token


class TestLogsAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(logs_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()

    def test_logs_no_token_returns_401(self):
        """无 token：/api/logs 已不在白名单，中间件直接 401（不再靠 require_role 兜）。"""
        r = self.client.get("/api/logs")
        self.assertEqual(r.status_code, 401)

    def test_logs_non_admin_cookie_returns_403(self):
        """非 admin 角色（会话有效）返回 403。"""
        self.client.cookies.set(COOKIE_NAME, _with_session("user"))
        r = self.client.get("/api/logs")
        self.assertEqual(r.status_code, 403)

    def test_logs_admin_cookie_returns_200(self):
        """admin 角色（会话有效）返回 200。"""
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        r = self.client.get("/api/logs")
        self.assertEqual(r.status_code, 200)
