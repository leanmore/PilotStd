# tests/test_session_invalidation.py
"""L-03：改密后失效既有会话（技术债阶段批次③，裁决 A1）。

## 背景

`SessionStore` 原先**没有按用户移除会话的能力**，故 `change_password` 落库后既有 JWT 仍
有效至 `expires_at` —— 攻击者窃取的 token 在改密后**依然可用**，即"改密"这一标准响应
对已泄露会话无效。该限制此前在两处代码注释中登记为已知限制。

## 本批修复

1. `SessionStore.remove_by_user(user_id) -> int`：线性扫描 `_store`（规模=活跃会话数）移除
   该用户全部会话，返回移除数；
2. **`add()` 改签名为显式 `user_id: int`**：原签名从 `user_info` dict 取 id，而全库 11 处
   调用**全部只传 `{"username": ...}`** → `session["user_id"]` 实为**用户名字符串**，
   使按 id 移除永远匹配不到。改签名后调用方无法漏传，且类型在边界处即被约束；
3. `change_password` 落库成功后调用 `remove_by_user`。

## 裁决 A1（本文件锁定）

连带失效**发起改密的那个会话** —— 改密成功后当前会话立即失效，用户需重新登录。
（若改为"保留当前会话"，需把 token 从 HTTP 层下沉到数据层，增加耦合。）
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

from docker.auth import COOKIE_NAME, SECRET, AuthMiddleware  # noqa: E402
from docker.session_store import SessionStore  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_session_invalidation(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


def _fresh_store() -> SessionStore:
    """构造独立实例（共享单例 `_store` 会被清空，避免污染其它用例）。"""
    store = SessionStore()
    with store._store_lock:
        store._store.clear()
    return store


def _make_token(sub: str = "1", role: str = "user") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": sub, "role": role, "iat": now, "exp": now + timedelta(hours=2)},
        SECRET,
        algorithm="HS256",
    )


class TestRemoveByUser(unittest.TestCase):
    """`SessionStore.remove_by_user` 的语义。"""

    def setUp(self):
        self.store = _fresh_store()

    def test_removes_matching_session(self):
        self.store.add("t1", 1, "alice", ttl_seconds=3600)
        self.assertEqual(self.store.remove_by_user(1), 1)
        self.assertIsNone(self.store.get("t1"))

    def test_removes_all_sessions_of_user(self):
        """★ 同一用户多设备（多个 token）→ 全部失效。"""
        self.store.add("t1", 1, "alice", ttl_seconds=3600)
        self.store.add("t2", 1, "alice", ttl_seconds=3600)
        self.store.add("t3", 1, "alice", ttl_seconds=3600)
        self.assertEqual(self.store.remove_by_user(1), 3)
        self.assertEqual(self.store.active_count, 0)

    def test_other_users_sessions_untouched(self):
        """★ 按 user_id 精确匹配 —— 不得波及他人（防"清空整个 store"这种过粗修法）。"""
        self.store.add("a1", 1, "alice", ttl_seconds=3600)
        self.store.add("b1", 2, "bob", ttl_seconds=3600)
        self.assertEqual(self.store.remove_by_user(1), 1)
        self.assertIsNone(self.store.get("a1"))
        self.assertIsNotNone(self.store.get("b1"), "bob 的会话不应被一并清除")

    def test_unknown_user_returns_zero(self):
        self.store.add("t1", 1, "alice", ttl_seconds=3600)
        self.assertEqual(self.store.remove_by_user(999), 0)
        self.assertIsNotNone(self.store.get("t1"))

    def test_user_id_type_is_int(self):
        """★ 回归护栏：`add()` 存入的必须是 **int**。

        原实现存的是 `user_info.get("user_id", user_info.get("username", ""))` —— 因调用方
        只传 `{"username": ...}`，实际存的是**字符串**，使 `== user_id` 永不匹配。
        判别力：把 `add()` 改回求 dict/字符串，本断言 FAIL。
        """
        self.store.add("t1", 1, "alice", ttl_seconds=3600)
        with self.store._store_lock:
            stored = self.store._store["t1"]["user_id"]
        self.assertIsInstance(stored, int, f"user_id 应为 int，实际 {type(stored).__name__}={stored!r}")

    def test_username_is_not_used_as_id(self):
        """★ 用户名不得被当作 id 匹配（原缺陷的精确复现）。"""
        self.store.add("t1", 1, "1", ttl_seconds=3600)  # username 恰为 "1"，但 id 是 int 1
        self.assertEqual(self.store.remove_by_user(1), 1)
        self.assertIsNone(self.store.get("t1"))

    def test_expired_session_also_removed(self):
        """`remove_by_user` 不区分是否过期，一律移除（过期项本就不该留存）。"""
        self.store.add("t1", 1, "alice", ttl_seconds=-1)  # 已过期
        self.assertEqual(self.store.remove_by_user(1), 1)


class TestChangePasswordInvalidatesSessions(unittest.TestCase):
    """`change_password` 落库成功后必须失效该用户全部会话（裁决 A1）。"""

    def setUp(self):
        self.store = _fresh_store()

    def _run_change_password(self, *, verify_ok: bool = True, user_row: dict | None = None):
        """驱动真实 `change_password`，仅桩掉外部依赖（DB / bcrypt / 用户查询）。"""
        import docker.users as U

        calls: list[str] = []
        with patch.object(U, "verify_user", return_value=verify_ok), \
             patch.object(U, "_validate_password", return_value=None), \
             patch.object(U, "_get_db", return_value=unittest.mock.MagicMock()), \
             patch.object(U, "get_password_hash", return_value="hash"), \
             patch.object(U, "generate_salt", return_value="salt"), \
             patch.object(U, "clear_must_change_password", side_effect=lambda n: calls.append("clear")), \
             patch.object(U, "get_user_by_username", return_value=user_row):
            return U.change_password("alice", "old", "newpassword"), calls

    def test_sessions_removed_on_success(self):
        """★ 核心判别：改密成功后该用户****全部****会话被移除（含当前会话——A1）。"""
        self.store.add("t1", 1, "alice", ttl_seconds=3600)
        self.store.add("t2", 1, "alice", ttl_seconds=3600)
        ok, _ = self._run_change_password(user_row={"id": 1, "username": "alice"})
        self.assertTrue(ok)
        self.assertIsNone(self.store.get("t1"), "改密后旧 token 必须立即失效")
        self.assertIsNone(self.store.get("t2"))
        self.assertEqual(self.store.active_count, 0)

    def test_other_users_not_affected(self):
        self.store.add("a1", 1, "alice", ttl_seconds=3600)
        self.store.add("b1", 2, "bob", ttl_seconds=3600)
        self._run_change_password(user_row={"id": 1, "username": "alice"})
        self.assertIsNotNone(self.store.get("b1"), "不得波及他人会话")

    def test_no_invalidation_when_old_password_wrong(self):
        """★ 旧密码错误 → 返回 False，**不得**失效会话（否则是拒绝服务）。"""
        self.store.add("t1", 1, "alice", ttl_seconds=3600)
        ok, _ = self._run_change_password(verify_ok=False, user_row={"id": 1, "username": "alice"})
        self.assertFalse(ok)
        self.assertIsNotNone(self.store.get("t1"), "验证失败时不应失效任何会话")

    def test_missing_user_row_does_not_crash(self):
        """用户行查不到（数据异常）→ 不抛异常，仍返回 True（落库已成功）。"""
        ok, _ = self._run_change_password(user_row=None)
        self.assertTrue(ok)


class TestEndToEndOldTokenRejected(unittest.TestCase):
    """端到端：改密后用**旧 token** 请求受保护端点 → 401（会话已失效）。

    走真实 `AuthMiddleware`（其 `_authenticate_session` 查 `get_session_store().get(token)`），
    故本用例锁定"改密 ⇒ 旧 token 立即被拒"这一链路级契约。
    """

    def setUp(self):
        self.store = _fresh_store()

    def test_old_token_gets_401_after_password_change(self):
        # 注意：`Request` 必须在**模块级**导入。本文件有 `from __future__ import annotations`，
        # 注解被字符串化，FastAPI 解析时查的是**模块全局**——若在函数内 import，
        # 它解析不到 `Request`，会把该参数当作**查询参数**（缺失即 422），而非请求对象。
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/api/__probe__")
        def _probe(request: Request):  # pragma: no cover
            return {"ok": True}

        token = _make_token()
        self.store.add(token, 1, "alice", ttl_seconds=3600)

        client = TestClient(app)
        client.cookies.set(COOKIE_NAME, token)
        first = client.get("/api/__probe__")
        self.assertEqual(
            first.status_code, 200, f"改密前应可通过；实际 {first.status_code} body={first.text[:200]}"
        )

        self.store.remove_by_user(1)  # = change_password 内的效果

        self.assertEqual(client.get("/api/__probe__").status_code, 401, "改密后旧 token 必须 401")
