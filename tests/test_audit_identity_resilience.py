# tests/test_audit_identity_resilience.py
"""`_resolve_audit_identity` 的**开库失败容错**（CI 修复，2026-10-02）。

## 缺陷（CI run 37009831322 实测）

`docker/users.py::_resolve_audit_identity` 的 docstring 承诺"数据异常 → 回落 unknown，
**不抛异常**"，但实现只在"查不到行"时回落；**开库本身失败**时异常会向上抛。
该函数只在 `auth.require_role` 的 **403 拒绝路径**上被调用，于是：

```
sqlite3.OperationalError: unable to open database file
```

把本该 **403** 的响应变成 **500**。CI 上 5 个鉴权用例因此全红
（`TestSettingsAuth/TestSystemAuth/TestTasksScanAuth/TestUsersWechatAuth::test_non_admin_403`
与 `TestChangePasswordSelfService::test_admin_endpoints_still_protected`）——
它们用 `FastAPI() + AuthMiddleware + 单个 router` 组装**最小应用**、**不建数据库**。

## 契约

审计身份的**附加值**（更可读的 username）**不得**反过来把拒绝响应打坏：
审计宁可记 `"unknown"`，也不得改变鉴权结果。
"""

from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.users import _resolve_audit_identity  # noqa: E402

FAILURE = sqlite3.OperationalError("unable to open database file")


class TestOpenFailureFallsBack(unittest.TestCase):
    """开库失败必须回落 `"unknown"`，不得抛异常。"""

    def test_operational_error_is_swallowed(self):
        """★ 核心：`sqlite3.OperationalError` 不得外向抛出。

        判别力：去掉 `_resolve_audit_identity` 里的 try/except → 本用例 FAIL。
        """
        with patch("docker.users.get_user_by_id", side_effect=FAILURE):
            uid, username = _resolve_audit_identity("1")
        self.assertEqual(uid, 1, "user_id 仍应可解析（来自 sub）")
        self.assertEqual(username, "unknown", "开库失败时 username 回落 unknown")

    def test_no_database_error_surfaces(self):
        """显式断言：不抛任何异常（含 sqlite3.Error 家族）。"""
        with patch("docker.users.get_user_by_id", side_effect=FAILURE):
            try:
                _resolve_audit_identity("42")
            except Exception as e:  # noqa: BLE001
                self.fail(f"开库失败不应抛异常，实际: {type(e).__name__}: {e}")

    def test_other_exceptions_also_swallowed(self):
        """任何异常都不得打坏鉴权结果（保守但正确：审计是旁路）。"""
        for exc in (RuntimeError("boom"), PermissionError("denied"), OSError("io")):
            with self.subTest(exc=type(exc).__name__):
                with patch("docker.users.get_user_by_id", side_effect=exc):
                    uid, username = _resolve_audit_identity("7")
                self.assertEqual((uid, username), (7, "unknown"))


class TestNormalPathsUnchanged(unittest.TestCase):
    """正常路径语义不得被容错改动影响。"""

    def test_found_user_returns_real_username(self):
        with patch("docker.users.get_user_by_id", return_value={"id": 1, "username": "mystdpilot"}):
            self.assertEqual(_resolve_audit_identity("1"), (1, "mystdpilot"))

    def test_missing_row_falls_back_to_unknown(self):
        with patch("docker.users.get_user_by_id", return_value=None):
            self.assertEqual(_resolve_audit_identity("1"), (1, "unknown"))

    def test_non_numeric_subject_does_not_touch_db(self):
        """旧格式 token（sub 即 username）**不查库**——即便库不可用也不受影响。"""
        with patch("docker.users.get_user_by_id", side_effect=FAILURE) as spy:
            self.assertEqual(_resolve_audit_identity("mystdpilot"), (None, "mystdpilot"))
        self.assertFalse(spy.called, "非数字 sub 不应触发查库")

    def test_non_string_subject(self):
        self.assertEqual(_resolve_audit_identity(None), (None, "unknown"))
        self.assertEqual(_resolve_audit_identity(123), (None, "unknown"))


if __name__ == "__main__":
    unittest.main()
