# tests/test_docker_auth.py — docker/auth.py 鉴权模块测试
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# auth.py 在非开发模式要求环境变量，测试前必须设置
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_testing")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.auth import COOKIE_NAME, AuthMiddleware

# 直接导入 auth 模块的组件
from docker.auth import router as auth_router


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
        r = self.client.post("/api/login", data={"password": "wrong"})
        self.assertEqual(r.status_code, 401)

    def test_login_correct_password_returns_ok_and_cookie(self):
        r = self.client.post(
            "/api/login", data={"password": os.environ["ADMIN_PASSWORD"]}
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertIn(COOKIE_NAME, r.cookies)

    def test_protected_with_valid_cookie_returns_200(self):
        # 先登录
        r = self.client.post(
            "/api/login", data={"password": os.environ["ADMIN_PASSWORD"]}
        )
        # 用返回的 cookie 访问受保护端点，附加 CSRF 头
        r.cookies.get(COOKIE_NAME)
        r2 = self.client.get("/api/protected", cookies=r.cookies)
        self.assertEqual(r2.status_code, 200)

    def test_protected_with_invalid_token_returns_401(self):
        """无效 token 返回 401（统一错误消息）"""
        r = self.client.get(
            "/api/protected", cookies={COOKIE_NAME: "invalid.token.here"}
        )
        self.assertEqual(r.status_code, 401)
        self.assertIn("认证失败", r.json()["error"])

    def test_logout_clears_cookie(self):
        """登出清除 Cookie（logout 在白名单中，无需 CSRF）。"""
        r = self.client.post(
            "/api/login", data={"password": os.environ["ADMIN_PASSWORD"]}
        )
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
        """GET /api/settings 在白名单中，无需鉴权"""
        r = self.client.get("/api/settings")
        self.assertEqual(r.status_code, 200)

    def test_put_settings_unauthenticated_returns_401(self):
        """PUT /api/settings 不在白名单，未登录返回 401"""
        r = self.client.put("/api/settings", json={"tasks": {}})
        self.assertEqual(r.status_code, 401, "PUT /api/settings 应先鉴权再放行")
