"""docker/api/users.py + wechat_ip.py 鉴权测试 — SEC-001 遗漏接口补测。

AST 脚本 check_decorator_order.py 发现的遗漏：users.py + wechat_ip.py 的端点
均为 admin 功能（用户管理/企业微信 IP），恢复 require_role。

## 本文件的分组（技术债阶段收尾更新）

**旧断言为何不再成立**：原 `_ENDPOINTS` 把 `PUT /api/users/password` 与其余端点**混在一组**，
断言"非 admin 一律 403"。但该端点的语义是"改**自己**的密码"——裁决 **D-3**（2026-09-26）
已明确移除它的 `@require_role("admin")`：普通用户被禁止更换自己的弱密码反而**降低**安全性。
用户隔离改由 `get_current_user_id(request)` 保证（只能改自己的）。

故 8 个端点现分两类：
- **`_ADMIN_ENDPOINTS`（7 项，users 3 + wechat_ip 4）**：带 `@require_role("admin")` → 非 admin 403；
- **`_SELF_SERVICE_ENDPOINTS`（1 项）**：`PUT /api/users/password`，无 `require_role`
  → 非 admin **可进入业务逻辑**，绝不返回 403。退出码由业务语义决定：
  弱密码 → 400（`_validate_password` 拒绝）、合法密码 → 200。

判别力：若有人把 `@require_role("admin")` 加回改密端点，`test_self_service_reachable_for_non_admin`
会因收到 403 而 FAIL —— 该用例同时是 D-3 裁决的护栏。
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api.users import router as users_router


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_users_wechat_auth(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass
from docker.api.wechat_ip import router as wechat_ip_router
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


# users 3（admin）+ wechat_ip 4（admin）= 7 项需 admin
_ADMIN_ENDPOINTS = [
    ("GET", "/api/users", None),
    ("POST", "/api/users", {"username": "testuser", "password": "testpass123", "role": "user"}),
    ("DELETE", "/api/users/99", None),
    ("GET", "/api/wechat-ip/config", None),
    ("PUT", "/api/wechat-ip/config", {}),
    ("POST", "/api/wechat-ip/check", None),
    ("GET", "/api/wechat-ip/status", None),
]

# 自助端点（裁决 D-3 移除 require_role）：改**自己**的密码
_SELF_SERVICE_PATH = "/api/users/password"

# 全部端点（两组合并）：用于"无 token → 401"——AuthMiddleware 对所有端点一致
_ENDPOINTS = _ADMIN_ENDPOINTS + [("PUT", _SELF_SERVICE_PATH, {"old_password": "old", "new_password": "newpass"})]


class TestUsersWechatAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(users_router)
        app.include_router(wechat_ip_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.client.headers.clear()
        self.client.app.dependency_overrides.clear()
        self.client.app.dependency_overrides[get_manager_dep] = lambda: MagicMock()

    def _set_cookie(self, role: str, with_session: bool = False):
        token = _make_token(role)
        if with_session:
            get_session_store().add(token, 1, "test", ttl_seconds=3600)
        self.client.cookies.set(COOKIE_NAME, token)

    def _set_csrf(self):
        self.client.cookies.set("csrf_token", "test_csrf")
        self.client.headers["X-CSRF-Token"] = "test_csrf"

    def test_no_token_401(self):
        """全部 8 个接口无 token → AuthMiddleware 401（认证层对两组一致）。"""
        for method, path, body in _ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 401, f"{method} {path} 无 token 应 401，实际 {r.status_code}")

    def test_non_admin_403(self):
        """**7 个 admin 端点**非 admin（有效 session + CSRF）→ require_role 403。

        注意：此处**不含** `PUT /api/users/password`——该端点为自助操作（裁决 D-3），
        其非 admin 行为由 `TestChangePasswordSelfService` 单独锁定。
        """
        self._set_cookie("user", with_session=True)
        self._set_csrf()
        for method, path, body in _ADMIN_ENDPOINTS:
            kwargs = {"json": body} if body is not None else {}
            r = self.client.request(method, path, **kwargs)
            self.assertEqual(r.status_code, 403, f"{method} {path} 非 admin 应 403，实际 {r.status_code}")

    def test_admin_200(self):
        """wechat_ip/status admin → 200（require_role 放行）。"""
        mock_mgr = self.client.app.dependency_overrides[get_manager_dep]()
        mock_mgr.wechat_ip_service.get_status.return_value = {"ok": True}

        self._set_cookie("admin", with_session=True)
        r = self.client.get("/api/wechat-ip/status")
        self.assertEqual(r.status_code, 200, f"admin 访问 wechat-ip/status 应 200，实际 {r.status_code}")


class TestChangePasswordSelfService(unittest.TestCase):
    """`PUT /api/users/password` 的自助语义（裁决 D-3）。

    该端点**无** `@require_role("admin")`：改的是**自己**的密码，隔离由
    `get_current_user_id(request)` 保证。故非 admin 必须能进入业务逻辑，绝不 403。

    **为何需要桩 `docker.api.users.get_user_by_id`**：端点首步是
    `user = get_user_by_id(user_id)`，查不到即 `400 用户不存在`。该函数走真实 DB
    （测试环境无 id=1 的行），**与角色无关**——实测 admin 也返回同一 400。
    故断言前必须把它桩掉，否则测的是"用户不存在"而非权限语义。
    """

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(users_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.client.headers.clear()
        self.client.app.dependency_overrides.clear()
        self.client.app.dependency_overrides[get_manager_dep] = lambda: MagicMock()
        self._set_cookie("user", with_session=True)
        self._set_csrf()

    def _set_cookie(self, role: str, with_session: bool = False):
        token = _make_token(role)
        if with_session:
            get_session_store().add(token, 1, "test", ttl_seconds=3600)
        self.client.cookies.set(COOKIE_NAME, token)

    def _set_csrf(self):
        self.client.cookies.set("csrf_token", "test_csrf")
        self.client.headers["X-CSRF-Token"] = "test_csrf"

    def _put(self, new_password: str, *, old_ok: bool = True):
        """以非 admin 身份改自己的密码；桩掉用户查询与底层改密。"""
        with patch("docker.api.users.get_user_by_id",
                   return_value={"id": 1, "username": "alice", "role": "user"}), \
             patch("docker.api.users.change_password", return_value=(old_ok, 1)):
            return self.client.put(
                _SELF_SERVICE_PATH,
                json={"old_password": "old", "new_password": new_password},
            )

    def test_self_service_reachable_for_non_admin(self):
        """★ 核心护栏：非 admin 改自己的密码 → **绝不 403**。

        判别力：把 `@require_role("admin")` 加回该端点 → 本用例收到 403 而 FAIL。
        这同时是裁决 D-3 的回归护栏。
        """
        r = self._put("newpass123")
        self.assertNotEqual(r.status_code, 403, "自助端点不应被 require_role 拦成 403（D-3 裁决）")

    def test_success_returns_200_for_non_admin(self):
        """非 admin + 合法新密码 + 旧密码正确 → 200（改密成功）。"""
        r = self._put("newpass123")
        self.assertEqual(r.status_code, 200, f"非 admin 改自己的密码应成功，实际 {r.status_code} {r.text[:120]}")

    def test_weak_password_400_for_non_admin(self):
        """非 admin + 弱密码（7 字符 < 8）→ 400（策略拒绝，非权限拒绝）。

        这解释并取代了旧断言：旧测试用 `newpass`（7 字符）却期望 403，
        而实际是端点自身的长度策略返回 400 —— 400 是**正确**行为。
        """
        r = self._put("newpass")
        self.assertEqual(r.status_code, 400, f"弱密码应 400，实际 {r.status_code}")
        self.assertNotEqual(r.status_code, 403)

    def test_wrong_old_password_400_for_non_admin(self):
        """非 admin + 旧密码错误 → 400（业务失败，非权限拒绝）。"""
        r = self._put("newpass123", old_ok=False)
        self.assertEqual(r.status_code, 400, f"旧密码错应 400，实际 {r.status_code}")

    def test_self_service_still_requires_authentication(self):
        """★ 自助 ≠ 匿名：无 token → 401（AuthMiddleware 不因移除 require_role 而放开）。"""
        self.client.cookies.clear()
        self.client.headers.clear()
        r = self.client.put(_SELF_SERVICE_PATH, json={"old_password": "o", "new_password": "newpass123"})
        self.assertEqual(r.status_code, 401, f"无 token 应 401，实际 {r.status_code}")

    def test_admin_endpoints_still_protected(self):
        """对照：同一个非 admin 会话访问 admin 端点仍 403（证明权限层未被削弱）。"""
        r = self.client.get("/api/users")
        self.assertEqual(r.status_code, 403, f"非 admin 访问 /api/users 应 403，实际 {r.status_code}")
