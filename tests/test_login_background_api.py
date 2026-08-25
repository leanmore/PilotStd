"""docker/api/upload.py 登录页背景图公开接口测试。

修复背景：LoginView 原通过 admin-only 的 GET /api/settings 获取登录页背景图 URL，
未登录（401）/ 非 admin（403）时拿不到，导致背景图请求延迟到登录后才发起甚至缺失。
新增公开接口 GET /api/login-background 解耦鉴权，仅暴露 appearance.login_bg 单字段，
不泄露其余系统配置。
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api.upload import router as upload_router
from docker.auth import AuthMiddleware
from docker.manager import get_manager_dep


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_login_background_api(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


class TestLoginBackgroundApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(upload_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.client.headers.clear()
        self.client.app.dependency_overrides.clear()
        self.mgr = MagicMock()
        self.client.app.dependency_overrides[get_manager_dep] = lambda: self.mgr

    def _cfg(self, value):
        self.mgr.cfg.get.return_value = value

    def test_no_token_returns_configured_url(self):
        """无 token（未登录）→ 200 + 配置的背景图 URL（白名单放行，不走 require_role）。"""
        self._cfg("/api/backgrounds/abc123.png")
        r = self.client.get("/api/login-background")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"url": "/api/backgrounds/abc123.png"})

    def test_no_token_empty_when_unset(self):
        """未配置背景图 → 200 + 空 url（前端走默认渐变降级）。"""
        self._cfg("")
        r = self.client.get("/api/login-background")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"url": ""})

    def test_response_does_not_leak_other_settings(self):
        """响应仅包含 url 字段，不泄露其余系统配置（如存储路径/站点配置/密钥掩码）。"""
        self._cfg("https://example.com/bg.jpg")
        r = self.client.get("/api/login-background")
        self.assertEqual(set(r.json().keys()), {"url"})

    def test_invalid_cookie_still_public(self):
        """伪造/过期 token 也不拦截（白名单在会话鉴权之前短路）。"""
        self.client.cookies.set("pilotstd_token", "invalid.token.here")
        self._cfg("/api/backgrounds/x.png")
        r = self.client.get("/api/login-background")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"url": "/api/backgrounds/x.png"})

    def test_non_string_config_falls_back_to_empty(self):
        """配置值非字符串（null/dict/list/int，防御）→ 返回空 url 而非 500 或序列化异常。"""
        for bad_value in (None, {}, [], 12345):
            with self.subTest(value=bad_value):
                self.mgr.cfg.get.return_value = bad_value
                r = self.client.get("/api/login-background")
                self.assertEqual(r.status_code, 200, f"bad_value={bad_value!r}")
                self.assertEqual(r.json(), {"url": ""}, f"bad_value={bad_value!r}")

    def test_explicit_null_login_bg_returns_empty(self):
        """login_bg 显式配置为 null（ConfigManager.get 返回 None 而非默认值）→ 空 url。"""
        self.mgr.cfg.get.return_value = None
        r = self.client.get("/api/login-background")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"url": ""})


if __name__ == "__main__":
    unittest.main()
