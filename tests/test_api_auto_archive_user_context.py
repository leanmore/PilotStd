"""多用户 P1：/api/auto、/api/archive 必须把当前用户带进通知上下文。

判据（见 docs/plans/2026-11-14-multiuser-mainline.md P1）：
两个用户各触发一次 auto 与 archive → `notification_log` 对应行 user_id 分别为两人，
`user_id=0` 行数为 0。本测试在 API 层锁住"上下文确实带着 user_id=1"，不落库。
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

from docker.api.archive import router as archive_router
from docker.api.auto import router as auto_router
from docker.auth import COOKIE_NAME, CSRF_HEADER, SECRET, AuthMiddleware
from docker.manager import get_manager_dep
from docker.session_store import get_session_store


class _FakeStore:
    def update_step(self, *args, **kwargs):
        return None


class _FakeMgr:
    def __init__(self):
        self.cfg = {"storage.root_dir": "", "storage.inbox_dir": "/inbox"}
        self.pipeline_store = _FakeStore()
        self.auto_calls = []
        self.archive_calls = []

    def auto_run(self, root_path, _adapter=None, context=None):
        self.auto_calls.append({"root_path": root_path, "context": context})
        return {"scan": 0}

    def archive_standards(self, parsed_list, word_source_root="", context=None):
        self.archive_calls.append({"parsed": parsed_list, "context": context})
        return {"moved": 0, "failed": 0, "details": []}


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_user_context(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""


def _with_session(role: str) -> str:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )
    get_session_store().add(token, 1, role)
    return token


CSRF = "csrf-test-token"


class TestAutoArchiveUserContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(auto_router)
        app.include_router(archive_router)
        cls.mgr = _FakeMgr()
        app.dependency_overrides[get_manager_dep] = lambda: cls.mgr
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.mgr.auto_calls.clear()
        self.mgr.archive_calls.clear()

    def test_auto_passes_user_context(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        self.client.cookies.set("csrf_token", CSRF)
        with patch("docker.api.auto.resolve_user_id", return_value=1):
            r = self.client.post("/api/auto", headers={CSRF_HEADER: CSRF})
        self.assertEqual(r.status_code, 200)
        ctx = self.mgr.auto_calls[0]["context"]
        self.assertIsNotNone(ctx, "auto_run 必须收到 NotificationContext（当前为 None ⇒ user_id=0）")
        self.assertEqual(ctx.user_id, 1)
        self.assertEqual(ctx.log_user_id, 1)

    def test_archive_passes_user_context(self):
        self.client.cookies.set(COOKIE_NAME, _with_session("admin"))
        payload = {
            "items": [{"source_path": "", "logical_code": "GB", "number": 1, "year": 2020}],
            "run_id": "run-1",
        }
        self.client.cookies.set("csrf_token", CSRF)
        with patch("docker.api.archive.resolve_user_id", return_value=1):
            r = self.client.post("/api/archive", json=payload, headers={CSRF_HEADER: CSRF})
        self.assertEqual(r.status_code, 200)
        ctx = self.mgr.archive_calls[0]["context"]
        self.assertIsNotNone(ctx, "archive_standards 必须收到 NotificationContext（当前为 None ⇒ user_id=0）")
        self.assertEqual(ctx.user_id, 1)
        self.assertEqual(ctx.log_user_id, 1)
