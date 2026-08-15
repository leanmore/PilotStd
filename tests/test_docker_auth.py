# tests/test_docker_auth.py — docker/auth.py 鉴权模块测试
import os
import sys
import unittest
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# auth.py 在非开发模式要求环境变量，测试前必须设置
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_testing")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")
os.environ.setdefault("SUPERUSER", "superadmin")

from docker.auth import COOKIE_NAME, AuthMiddleware
from docker.auth import router as auth_router


@pytest.fixture(autouse=True)
def isolated_user_db(tmp_path):
    """自动将 docker.users 和 docker.auth 切换到临时数据库，确保测试互不干扰。"""
    import docker.auth
    import docker.users
    from pilotstd.core.db.database import Database

    # conftest.py 在收集阶段已加载 pilotstd（此时 SUPERUSER 未设置），
    # 导致 docker.users / docker.auth 的 SUPERUSER_USERNAME 被缓存为 None。
    # 必须在 fixture 中修正。
    _su_name = os.environ.get("SUPERUSER", "superadmin")
    docker.users.SUPERUSER_USERNAME = _su_name
    docker.auth.SUPERUSER_USERNAME = _su_name

    test_db: Path = tmp_path / "test_users.db"

    # 1. 创建临时数据库实例（含完整 schema 迁移）
    db = Database(str(test_db))

    # 2. 直接注入 users 模块的全局缓存，所有 _get_db() 调用返回此实例
    docker.users._db_instance = db

    # 3. 重置 auth 模块初始化标志，确保登录路由不会跳过表创建
    docker.auth._init_done = False

    # 4. 初始化用户表和登录尝试表
    docker.users.init_users_table()
    docker.users.init_login_attempts_table()

    yield


class TestAuthModule(unittest.TestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(auth_router)

        # 注册 settings 路由——验证 PUT 非白名单需鉴权
        from docker.api.settings import router as settings_router

        app.include_router(settings_router)

        @app.get("/api/protected")
        def protected():
            return {"ok": True}

        @app.get("/api/health")
        def health():
            return {"status": "ok"}

        cls.client = TestClient(app)

    def setUp(self):
        """每个测试前清除残留 cookie。"""
        self.client.cookies.clear()

    def test_health_whitelisted_no_auth(self):
        """健康检查在白名单中，不需要鉴权"""
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)

    def test_protected_no_cookie_returns_401(self):
        """未登录访问受保护端点返回 401（统一错误消息）"""
        r = self.client.get("/api/protected")
        self.assertEqual(r.status_code, 401)
        self.assertIn("认证失败", r.json()["error"])

    def test_login_wrong_password_returns_401(self):
        r = self.client.post("/api/login", data={"username": "superadmin", "password": "wrong"})
        self.assertEqual(r.status_code, 401)

    @pytest.mark.xdist_group("auth")
    def test_login_correct_password_returns_ok_and_cookie(self):
        r = self.client.post("/api/login", data={"username": "superadmin", "password": os.environ["ADMIN_PASSWORD"]})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertIn(COOKIE_NAME, r.cookies)

    def test_protected_with_valid_cookie_returns_200(self):
        # 先登录
        r = self.client.post("/api/login", data={"username": "superadmin", "password": os.environ["ADMIN_PASSWORD"]})
        # 用返回的 cookie 访问受保护端点，附加 CSRF 头
        r.cookies.get(COOKIE_NAME)
        r2 = self.client.get("/api/protected", cookies=r.cookies)
        self.assertEqual(r2.status_code, 200)

    def test_protected_with_invalid_token_returns_401(self):
        """无效 token 返回 401（统一错误消息）"""
        r = self.client.get("/api/protected", cookies={COOKIE_NAME: "invalid.token.here"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("认证失败", r.json()["error"])

    def test_logout_clears_cookie(self):
        """登出清除 Cookie（logout 在白名单中，无需 CSRF）。"""
        r = self.client.post("/api/login", data={"username": "superadmin", "password": os.environ["ADMIN_PASSWORD"]})
        r2 = self.client.post("/api/logout", cookies=r.cookies)
        self.assertEqual(r2.status_code, 200)
        # 登出后 Cookie 被清除
        cookie = r2.cookies.get(COOKIE_NAME)
        self.assertTrue(cookie is None or cookie == "" or cookie == '""')

    def test_spa_non_api_path_passes_through(self):
        """SPA 静态文件（非 /api/）不拦截"""
        r = self.client.get("/index.html")
        self.assertNotEqual(r.status_code, 401)  # 不拦截，返回 404 或其他

    def test_get_settings_whitelisted_no_auth(self):
        """SEC-001: GET /api/settings 已从 AUTH_WHITELIST 移除，无 token 走 AuthMiddleware 返回 401。"""
        r = self.client.get("/api/settings")
        self.assertEqual(r.status_code, 401)

    def test_put_settings_unauthenticated_returns_401(self):
        """PUT /api/settings 不在白名单，未登录返回 401"""
        r = self.client.put("/api/settings", json={"tasks": {}})
        self.assertEqual(r.status_code, 401, "PUT /api/settings 应先鉴权再放行")
