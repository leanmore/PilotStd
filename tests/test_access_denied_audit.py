# tests/test_access_denied_audit.py
"""L-04：`require_role` 的 ACCESS_DENIED 审计载荷修复（技术债阶段批次②）。

## 背景

`docker/auth.py::require_role` 原写：
```python
username = payload.get("sub", "unknown")          # sub 是 user_id（v3.0 起）
detail={"...", "username": username}              # 故 detail["username"] 恒为 "1"
```
JWT 侧 `_generate_token` 写的是 `"sub": str(user_id)`，故 `detail["username"]` 落到
`audit_logs.detail` 里是用户 id 的字符串形式，而非可读用户名。

**影响面经实测确认低于"数据缺失"**：`write_audit` 的 `user_id` 列由 ContextVar 提供，而
HTTP 中间件（`docker/auth.py` 的 `AuthMiddleware.dispatch`）已在 `call_next` 之前用同一
`sub` 注入 `set_current_user_id(user_id)` —— 故 `audit_logs.user_id` 列**原本就是正确的**；
错的只是 `detail["username"]` 的值（可读性缺陷）。

## 修复要点（本文件判别）

1. `detail["username"]` 必须是**真实用户名**（按 id 反查 `users` 表）；
2. 反查**只在拒绝路径**发生（正常授权不查库）→ 由计数用例锁定；
3. 旧格式 token（`sub=username`）走 else 分支，不查库；
4. `write_audit` 显式传 `user_id`，使审计列与 detail 一致。
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware, require_role  # noqa: E402
from docker.session_store import get_session_store  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_access_denied(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


def _make_token(role: str, sub: str = "1") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": sub, "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


# 一个只要求 admin 的探针端点，避免依赖具体业务路由
app = FastAPI()
app.add_middleware(AuthMiddleware)


@app.get("/api/__probe_admin_only__")
@require_role("admin")
def _probe(request: Request):  # pragma: no cover - 仅用于触发装饰器
    return {"ok": True}


def _add_session(token: str) -> None:
    get_session_store().add(token, 1, "test", ttl_seconds=3600)


class TestAccessDeniedAuditPayload(unittest.TestCase):
    """审计载荷：detail["username"] 必须是真实用户名，不是 user_id。"""

    def setUp(self):
        self.client = TestClient(app)
        self.client.cookies.clear()
        self.client.headers.clear()

    def _set(self, role: str, sub: str = "1"):
        token = _make_token(role, sub=sub)
        _add_session(token)
        self.client.cookies.set(COOKIE_NAME, token)

    def test_username_is_real_name_not_user_id(self):
        """★ 核心判别：detail["username"] == 真实用户名（"admin"），而非 "1"。

        判别力：还原 `detail["username"] = payload["sub"]` 后，该字段变回 "1" → 本用例 FAIL。
        """
        self._set("user", sub="1")
        with patch("docker.users.get_user_by_id", return_value={"id": 1, "username": "alice", "role": "user"}) as spy:
            with patch("docker.auth.write_audit") as wa:
                r = self.client.get("/api/__probe_admin_only__")
        self.assertEqual(r.status_code, 403)
        wa.assert_called_once()
        detail = wa.call_args.kwargs["detail"]
        self.assertEqual(detail["username"], "alice", "detail.username 应为反查到的真实用户名")
        self.assertNotEqual(detail["username"], "1", "不得回落为 user_id 字符串")
        spy.assert_called_once_with(1)

    def test_write_audit_receives_explicit_user_id(self):
        """★ 显式传 user_id=1，使审计列与 detail 一致（不依赖 ContextVar）。"""
        self._set("user", sub="1")
        with patch("docker.users.get_user_by_id", return_value={"id": 1, "username": "alice", "role": "user"}):
            with patch("docker.auth.write_audit") as wa:
                self.client.get("/api/__probe_admin_only__")
        self.assertEqual(wa.call_args.kwargs.get("user_id"), 1)

    def test_lookup_only_on_denied_path(self):
        """★ 性能契约：正常授权路径**不查库**（反查只在拒绝分支）。

        判别力：把反查移到 `if` 之外后，admin 请求也会调用 get_user_by_id → 本用例 FAIL。
        """
        self._set("admin", sub="1")
        with patch("docker.users.get_user_by_id") as spy:
            with patch("docker.auth.write_audit") as wa:
                r = self.client.get("/api/__probe_admin_only__")
        self.assertEqual(r.status_code, 200, "admin 应放行")
        spy.assert_not_called()
        wa.assert_not_called()

    def test_legacy_token_sub_is_username(self):
        """旧格式 token（sub=username）→ 不查库，detail["username"] 用 sub 本身。"""
        self._set("user", sub="legacy_user")
        with patch("docker.users.get_user_by_id") as spy:
            with patch("docker.auth.write_audit") as wa:
                self.client.get("/api/__probe_admin_only__")
        spy.assert_not_called()
        self.assertEqual(wa.call_args.kwargs["detail"]["username"], "legacy_user")

    def test_unknown_user_id_falls_back_to_unknown(self):
        """id 无对应行（数据异常）→ 不抛异常，username 回落 "unknown"。"""
        self._set("user", sub="999")
        with patch("docker.users.get_user_by_id", return_value=None):
            with patch("docker.auth.write_audit") as wa:
                r = self.client.get("/api/__probe_admin_only__")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(wa.call_args.kwargs["detail"]["username"], "unknown")


class TestNoGetCurrentUsernameAlias(unittest.TestCase):
    """死代码清理护栏：`get_current_username` 别名已删除。"""

    def test_alias_removed(self):
        """判别力：重新加回该别名（它返回 user_id 却名为 username）时本用例 FAIL。"""
        import docker.auth as auth_mod

        self.assertFalse(
            hasattr(auth_mod, "get_current_username"),
            "get_current_username 是误导性别名（返回 user_id），已作为死代码删除，不得加回",
        )


class TestUserApiParamNaming(unittest.TestCase):
    """L-04 外溢：`docker/api/user.py` 的 7 处参数名为 user_id（非 username）。"""

    def test_params_named_user_id(self):
        import ast
        import pathlib

        src = pathlib.Path(docker_user_api_path()).read_text(encoding="utf-8")
        bad: list[str] = []
        checked = 0
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.FunctionDef):
                continue
            has_dep = "get_current_user_id" in ast.unparse(node)
            if not has_dep:
                continue
            checked += 1
            names = [a.arg for a in node.args.args]
            if "username" in names:
                bad.append(node.name)
        self.assertEqual(checked, 7, f"应检查到 7 个函数，实际 {checked}")
        self.assertEqual(bad, [], f"以下函数仍用 username 命名 user_id：{bad}")


def docker_user_api_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docker", "api", "user.py")
