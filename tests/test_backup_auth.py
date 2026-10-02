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
from pathlib import Path
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


class TestBackupListRequiresAdmin(unittest.TestCase):
    """`GET /api/backup/list` 的 admin 门控（收尾 B）。

    列表虽不含备份**内容**，但**备份文件的存在性本身是信息**：文件名带时间戳，可据此推断
    系统状态与备份频度。普通用户无需知道。
    """

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

    def test_non_admin_403(self):
        """★ 核心判别：非 admin 列备份 → 403。

        判别力：移除 `@require_role("admin")` → 端点体执行、返回 200，本用例 FAIL。
        """
        self._set_cookie("user")
        r = self.client.get("/api/backup/list")
        self.assertEqual(r.status_code, 403, f"非 admin 应 403，实际 {r.status_code}")

    def test_admin_passes_authorization(self):
        """admin → 通过授权层（不因 403 被拦）。"""
        self._set_cookie("admin")
        r = self.client.get("/api/backup/list")
        self.assertNotEqual(r.status_code, 403, "admin 不应被授权层拒绝")

    def test_no_token_401(self):
        """无 token → 401（GET 不需 CSRF）。"""
        r = self.client.get("/api/backup/list")
        self.assertEqual(r.status_code, 401, f"无 token 应 401，实际 {r.status_code}")


class TestBackupAuthorizationGuards(unittest.TestCase):
    """静态护栏：端点装饰器齐全 + G-043 扫描面的事实登记。"""

    def test_both_backup_endpoints_require_admin(self):
        """两端点均须 `@require_role("admin")`（收尾 B 的目标状态）。

        判别力：移除任一端点的装饰器 → 本用例 FAIL。
        """
        import ast
        from pathlib import Path as _Path

        src = (_Path(__file__).resolve().parent.parent / "docker" / "api" / "backup.py").read_text(encoding="utf-8")
        routed = 0
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.FunctionDef):
                continue
            decs = [ast.unparse(d) for d in node.decorator_list]
            if not any("router." in d for d in decs):
                continue  # 非路由函数（如 _get_backup_dir）
            routed += 1
            self.assertTrue(
                any("require_role" in d for d in decs),
                f"路由函数 {node.name} 缺 @require_role('admin')；装饰器={decs}",
            )
        self.assertEqual(routed, 2, f"backup.py 应有 2 个路由端点，实际 {routed}")

    def test_g043_scan_scope_includes_backup_and_gate_passes(self):
        """事实登记 + 门禁守约：`docker/api/backup.py` **在** G-043 扫描面内，且门禁通过。

        G-043 的 `_scan_targets()` 扫 `docker/api/` 下**全部** `.py` + `docker/auth.py`，
        故 `docker/api/backup.py` **确在其中**（此前误判为"不在扫描面"，本用例更正）。

        它不构成违规的原因：G-043 只对 `SENSITIVE_ROUTES` **清单内**的路由要求函数可达
        `write_audit`。备份的**写**端点 `POST /api/backup/create` 已在清单中且已接线
        （写 `BACKUP_CREATE` / `BACKUP_CREATE_FAILED`）；**读**端点 `GET /api/backup/list`
        不在清单中——只读不改状态，无留痕价值（其越权由 `@require_role` 拦，
        `require_role` 拒绝时写 `ACCESS_DENIED`）。

        判别力：若把 `create_backup` 的 `write_audit` 调用删掉，G-043 会 FAIL → 本用例 FAIL。
        """
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import check_sensitive_endpoint_audit as gate  # noqa: PLC0415

        scanned = {str(p).replace("\\", "/") for p in gate._scan_targets()}
        self.assertTrue(
            any(p.endswith("docker/api/backup.py") for p in scanned),
            "docker/api/backup.py 应在 G-043 扫描面内（该门禁扫 docker/api/ 全部 .py）",
        )
        routes, _module_level = gate.collect_routes()
        self.assertIn(
            "POST /api/backup/create", routes,
            "备份写端点须在 G-043 扫描到的路由集合中（SENSITIVE_ROUTES 成员）",
        )
        _rel, _lineno, node, reaches = routes["POST /api/backup/create"]
        self.assertTrue(reaches, f"{node.name} 必须函数可达 write_audit（G-043 判定）")

    def test_admin_gated_endpoints_have_request_param(self):
        """★ 易踩陷阱护栏：带 `@require_role` 的端点**必须有 `request: Request` 参数**。

        `require_role` 的实现是遍历 `args`/`kwargs` 找 `Request` 对象来读 Cookie 中的 JWT
        （`docker/auth.py` 的 wrapper）。若端点签名无 `request`，wrapper 取不到请求对象 →
        `current_role` 回落默认 `"user"` → **连 admin 也被 403**。

        本批实测踩到该陷阱：给 `GET /api/backup/list` 加 `@require_role("admin")` 后
        admin 仍得 403，直到补上 `request: Request` 参数。
        （这也是当初 `POST /api/backup/create` 需要新增 `request` 参数的同一原因。）

        判别力：把任一端点的 `request: Request` 参数删掉 → 本用例 FAIL。
        """
        import ast
        from pathlib import Path as _Path

        root = _Path(__file__).resolve().parent.parent
        offenders: list[str] = []
        checked = 0
        for rel in ("docker/api/backup.py", "docker/api/users.py", "docker/api/wechat_ip.py"):
            src = (root / rel).read_text(encoding="utf-8")
            for node in ast.walk(ast.parse(src)):
                if not isinstance(node, ast.FunctionDef):
                    continue
                decs = [ast.unparse(d) for d in node.decorator_list]
                if not any("require_role" in d for d in decs):
                    continue
                checked += 1
                param_names = [a.arg for a in node.args.args]
                if "request" not in param_names:
                    offenders.append(f"{rel}::{node.name} (params={param_names})")
        self.assertGreater(checked, 0, "未检查到任何带 require_role 的端点，锚点可能失效")
        self.assertEqual(
            offenders, [],
            f"以下端点带 @require_role 但缺 `request: Request` 参数，会让 admin 也被 403：{offenders}",
        )
