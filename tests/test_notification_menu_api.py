"""A-27.3：菜单管理端点的端到端鉴权（GET status / POST sync）。

覆盖：无会话 401（中间件层）、普通用户 403（require_role 层）、admin 200、
同步失败 400 可读原因、缺参 422、非 admin 不触发渠道同步（sync_channel 不被调用）。
真实渠道调用被 patch，避免测试外网/凭证。
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api import notification_menu
from docker.api.notification_menu import router as menu_router
from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware
from docker.session_store import get_session_store

STATUS_ROWS = [
    {"channel": "wechat", "supported": True, "types": ["a", "b"], "enabled": True, "last_synced": None},
    {"channel": "feishu", "supported": True, "types": ["a"], "enabled": False, "last_synced": None},
    {"channel": "telegram", "supported": True, "types": ["commands"], "enabled": True, "last_synced": None},
    {"channel": "dingtalk", "supported": False, "types": [], "enabled": False, "last_synced": None},
]


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_menu_auth(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""


def _token(role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


def _with_session(role: str) -> str:
    token = _token(role)
    get_session_store().add(token, 1, role)
    return token


def _status_patch():
    return patch.multiple(
        notification_menu,
        menu_status=lambda _cfg: STATUS_ROWS,
        ConfigManager=lambda: object(),
    )


class TestMenuAuth(unittest.TestCase):
    """路由层：不挂中间件，只验 require_role 的 403/200。"""

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(menu_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()

    def test_status_without_cookie_is_forbidden(self):
        r = self.client.get("/api/notification/menu/status")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "forbidden")

    def test_status_non_admin_is_forbidden(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("user"))
        r = self.client.get("/api/notification/menu/status")
        self.assertEqual(r.status_code, 403)

    def test_status_admin_ok(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        with _status_patch():
            r = self.client.get("/api/notification/menu/status")
        self.assertEqual(r.status_code, 200)
        channels = r.json()["channels"]
        self.assertEqual([c["channel"] for c in channels], ["wechat", "feishu", "telegram", "dingtalk"])
        self.assertTrue(channels[0]["supported"])
        self.assertFalse(channels[3]["supported"])

    def test_sync_admin_ok(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        with patch.multiple(
            notification_menu,
            sync_channel=lambda channel, _cfg: {"ok": True, "channel": channel, "changed": True},
            ConfigManager=lambda: object(),
            write_audit=lambda **kwargs: None,
        ):
            r = self.client.post("/api/notification/menu/sync?channel=wechat")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(),
            {"ok": True, "channel": "wechat", "changed": True, "code": "", "error": "", "skipped": ""},
        )

    def test_sync_failure_returns_400_with_reason(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        with patch.multiple(
            notification_menu,
            sync_channel=lambda channel, _cfg: {
                "ok": False,
                "channel": channel,
                "changed": False,
                "error": "no credentials",
            },
            ConfigManager=lambda: object(),
            write_audit=lambda **kwargs: None,
        ):
            r = self.client.post("/api/notification/menu/sync?channel=feishu")
        self.assertEqual(r.status_code, 400)
        self.assertIn("no credentials", r.json()["detail"])

    def test_sync_non_admin_forbidden_and_not_executed(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("user"))
        with patch.object(notification_menu, "sync_channel") as sync:
            r = self.client.post("/api/notification/menu/sync?channel=wechat")
        self.assertEqual(r.status_code, 403)
        sync.assert_not_called()

    def test_sync_missing_channel_is_422(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        r = self.client.post("/api/notification/menu/sync")
        self.assertEqual(r.status_code, 422)


class TestMenuMiddleware(unittest.TestCase):
    """中间件层：无会话必须在进入路由前 401。"""

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(menu_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()

    def test_status_without_session_is_401(self):
        r = self.client.get("/api/notification/menu/status")
        self.assertEqual(r.status_code, 401)

    def test_status_admin_session_ok(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        with _status_patch():
            r = self.client.get("/api/notification/menu/status")
        self.assertEqual(r.status_code, 200)
