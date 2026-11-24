"""tests/test_notification_log_scope.py — `_log_scope` 的用户作用域 SQL（NEW-43，2026-11-24）。

背景：NEW-43 记录 30 个后端模块在 `tests/` 里无任何文本引用，其中
`pilotstd/core/notification/_log_scope.py` 是**通知可见性的核心**：
「谁能看到哪条通知」「全部已读会不会清掉别人的未读」都靠它生成的 SQL 片段。
此前完全无测试覆盖。

本测试锁住 `user_clause()` 的三种口径（这是 `mark_one` / `mark_all` / `unread`
共用的唯一真相源）：
  1. `user_id=None` → 无过滤（全局视角）
  2. `user_id=N` 且 `include_system=False` → 只看本人（**不得**含系统通知）
  3. `user_id=N` 且 `include_system=True` → 本人 + 系统（user_id=0 或 NULL）
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.core.notification import _log_scope  # noqa: E402


def test_user_clause_none_has_no_filter():
    """无 user_id → 空片段、空参数（全局视角）。"""
    clause, params = _log_scope.user_clause(None, include_system=False)
    assert clause == ""
    assert params == []


def test_user_clause_self_only():
    """有 user_id 且不含系统 → 只匹配本人。"""
    clause, params = _log_scope.user_clause(7, include_system=False)
    assert "user_id = ?" in clause
    assert "user_id = 0" not in clause
    assert "IS NULL" not in clause
    assert params == [7]


def test_user_clause_with_system():
    """有 user_id 且含系统 → 本人 + user_id=0 + NULL（管理员视角）。"""
    clause, params = _log_scope.user_clause(7, include_system=True)
    assert "user_id = ?" in clause
    assert "user_id = 0" in clause
    assert "IS NULL" in clause
    # 参数只有一个 user_id（0/NULL 是字面量，不占位）
    assert params == [7]


def test_mark_one_scopes_by_user():
    """`mark_one` 带 user_id 时 SQL 必须含用户过滤（不能清别人的未读）。"""
    calls: list[tuple[str, tuple]] = []

    class _Cur:
        rowcount = 1

    class _Db:
        def execute(self, sql, params=()):
            calls.append((sql, tuple(params)))
            return _Cur()

    n = _log_scope.mark_one(_Db(), log_id=42, user_id=7, include_system=False)

    assert n == 1
    sql, params = calls[0]
    assert "id = ?" in sql
    assert "user_id = ?" in sql
    assert params == (42, 7)


def test_mark_all_without_user_touches_all():
    """`mark_all` 无 user_id → 不加用户过滤（全局全部已读）。"""
    calls: list[tuple[str, tuple]] = []

    class _Db:
        def execute(self, sql, params=()):
            calls.append((sql, tuple(params)))

    _log_scope.mark_all(_Db(), user_id=None, include_system=False)

    sql, params = calls[0]
    assert "WHERE" not in sql or "user_id" not in sql
    assert params == ()


def test_mark_all_with_user_is_scoped():
    """`mark_all` 带 user_id → 必须加用户过滤（否则「全部已读」清掉别人的未读）。"""
    calls: list[tuple[str, tuple]] = []

    class _Db:
        def execute(self, sql, params=()):
            calls.append((sql, tuple(params)))

    _log_scope.mark_all(_Db(), user_id=7, include_system=False)

    sql, params = calls[0]
    assert "user_id = ?" in sql
    assert "is_read = 0" in sql
    assert params == (7,)


def test_unread_uses_same_clause():
    """`unread` 必须与 `mark_all` 同口径（否则计数与操作不一致）。"""
    seen: list[tuple[str, tuple]] = []

    class _Db:
        def fetchone(self, sql, params=()):
            seen.append((sql, tuple(params)))
            return {"cnt": 3}

    assert _log_scope.unread(_Db(), user_id=7, include_system=False) == 3
    sql, params = seen[0]
    assert "is_read = 0" in sql
    assert "user_id = ?" in sql
    assert params == (7,)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
