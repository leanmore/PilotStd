# tests/test_backup_auth.py
"""docker/api/backup.py 授权测试 — 手动备份端点的 admin 门控（技术债阶段批次①）。

## 背景（本批修复的越权）

`POST /api/backup/create` 原本**无 `@require_role`**。全局 `AuthMiddleware`
（`docker/app.py:288`）只保证"已认证"，不保证角色 —— 故**任意登录用户**都能触发创建
**含全量数据库内容**（用户表 / 密码哈希 / 审计日志 / 通知渠道凭证）的备份文件。

`/api/backup` **不在 `AUTH_WHITELIST`**（`docker/auth.py:181-192` 九项白名单中无它），
故该端点受 AuthMiddleware 的 session 认证覆盖 —— 即问题不是"可匿名访问"，
而是"**缺授权（越权）**"。

## 判别力

`test_non_admin_403` 是本批的核心断言：**注入坏形态（移除 `@require_role("admin")`）
后该用例必须 FAIL**（非 admin 会拿到 200/500 而非 403）。
"""

from __future__ import annotations

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

from docker.api.backup import router as backup_router  # noqa: E402
from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware  # noqa: E402
from docker.manager import get_manager_dep  # noqa: E402
from docker.session_store import get_session_store  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_backup_auth(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


def _make_token(role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "1", "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


def _mock_mgr() -> MagicMock:
    """mgr 替身：让 backup 走成功路径（返回非空路径）。"""
    mgr = MagicMock()
    mgr.db.path = os.path.join(os.getcwd(), "pilotstd.db")
    mgr.db.backup.return_value = os.path.join(os.getcwd(), "pilotstd_manual_test.bak")
    return mgr


class TestBackupCreateAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(backup_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.client.headers.clear()
        self.client.app.dependency_overrides.clear()
        self.client.app.dependency_overrides[get_manager_dep] = _mock_mgr

    def _set_cookie(self, role: str, with_session: bool = True):
        token = _make_token(role)
        if with_session:
            get_session_store().add(token, 1, "test", ttl_seconds=3600)
        self.client.cookies.set(COOKIE_NAME, token)

    def _set_csrf(self):
        self.client.cookies.set("csrf_token", "test_csrf")
        self.client.headers["X-CSRF-Token"] = "test_csrf"

    # ── 核心判别：非 admin 必须 403 ──────────────────────────────────────────

    def test_non_admin_403(self):
        """★ 非 admin（有效 session + CSRF）→ 403。

        判别力：移除 `@require_role("admin")` 后，请求会直达端点体、返回 200/500，
        本断言 FAIL —— 即该用例能真正区分"有授权门控"与"无授权门控"。
        """
        self._set_cookie("user")
        self._set_csrf()
        r = self.client.post("/api/backup/create")
        self.assertEqual(r.status_code, 403, f"非 admin 应 403，实际 {r.status_code}")

    def test_admin_passes_authorization(self):
        """admin（有效 session + CSRF）→ 通过授权层（不因 403 被拦）。"""
        self._set_cookie("admin")
        self._set_csrf()
        r = self.client.post("/api/backup/create")
        self.assertNotEqual(r.status_code, 403, "admin 不应被授权层拒绝")

    def test_no_token_401(self):
        """无 token → AuthMiddleware 401（/api/backup 不在白名单）。"""
        r = self.client.post("/api/backup/create")
        self.assertEqual(r.status_code, 401, f"无 token 应 401，实际 {r.status_code}")

    def test_missing_csrf_403(self):
        """admin 但缺 CSRF → 403（AuthMiddleware 的写方法 CSRF 校验）。"""
        self._set_cookie("admin")
        # 不设 CSRF
        r = self.client.post("/api/backup/create")
        self.assertEqual(r.status_code, 403, f"缺 CSRF 应 403，实际 {r.status_code}")

    def test_whitelist_does_not_cover_backup(self):
        """回归护栏：`/api/backup` 不得被加入 AUTH_WHITELIST。

        判别力：若有人为"修 401"而把 `/api/backup` 加进白名单，本用例 FAIL。
        """
        from docker.auth import AUTH_WHITELIST

        for prefix, _methods in AUTH_WHITELIST:
            self.assertFalse(
                "/api/backup".startswith(prefix),
                f"/api/backup 不应被白名单前缀 {prefix!r} 覆盖（会使备份端点可匿名访问）",
            )
