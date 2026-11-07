# 模块：通知日志的用户/系统可见性 SQL 片段（避免 _manager_ops 继续膨胀）
"""通知日志的用户作用域与系统通知可见性。"""

from __future__ import annotations

from typing import Any

_TABLE = "notification_log"


def user_clause(user_id: int | None, include_system: bool) -> tuple[str, list[Any]]:
    """返回 user_id 过滤片段；管理员 include_system 时纳入 0/NULL 系统通知。"""
    if user_id is None:
        return "", []
    if include_system:
        return "(user_id = ? OR user_id = 0 OR user_id IS NULL)", [user_id]
    return "user_id = ?", [user_id]


def mark_one(db: Any, log_id: int, user_id: int | None, include_system: bool) -> int:
    """标记一条；返回真实受影响行数。"""
    if user_id is None:
        cur = db.execute(f"UPDATE {_TABLE} SET is_read = 1 WHERE id = ?", (log_id,))
    else:
        clause, params = user_clause(user_id, include_system)
        cur = db.execute(
            f"UPDATE {_TABLE} SET is_read = 1 WHERE id = ? AND {clause}",
            (log_id, *params),
        )
    return int(cur.rowcount or 0)


def mark_all(db: Any, user_id: int | None, include_system: bool) -> None:
    """标记全部未读；管理员 include_system 时同时清系统通知。"""
    if user_id is None:
        db.execute(f"UPDATE {_TABLE} SET is_read = 1")
        return
    clause, params = user_clause(user_id, include_system)
    db.execute(
        f"UPDATE {_TABLE} SET is_read = 1 WHERE is_read = 0 AND {clause}",
        tuple(params),
    )


def unread(db: Any, user_id: int | None, include_system: bool) -> int:
    """未读数；管理员 include_system 时包含系统通知。"""
    if user_id is None:
        row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM {_TABLE} WHERE is_read = 0")
    else:
        clause, params = user_clause(user_id, include_system)
        row = db.fetchone(
            f"SELECT COUNT(*) AS cnt FROM {_TABLE} WHERE is_read = 0 AND {clause}",
            tuple(params),
        )
    return int(row["cnt"]) if row else 0
