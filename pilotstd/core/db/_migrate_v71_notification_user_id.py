# 模块：v71 通知日志/队列增加 user_id
"""为 notification_log / notification_queue 增加 user_id（A-21 数据模型层）。

中间状态安全说明：v71 落地后、读写路径改造前，所有 user_id 恒为 1，
功能上仍是单用户；这是**预期中间态**，不是“列加了没过滤”的 bug。

缺表跳过：部分历史故障库/局部测试夹具只含相关表（如 v52 故障库只建 user_favorites），
迁移不应因缺少通知表而失败；表存在时正常加列/回填/建索引。
"""

from __future__ import annotations

from typing import Any

from ._constants import migration

_TABLES = ("notification_log", "notification_queue")


@migration(71)
def _migrate_v71_notification_user_id(db: Any) -> None:
    """加 user_id 列 + 回填 1 + 用户维度索引（幂等，缺表跳过）。"""
    for table in _TABLES:
        rows = db.fetchall(f"PRAGMA table_info({table})")
        if not rows:
            continue
        columns = {row["name"] for row in rows}
        if "user_id" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
        db.execute(f"UPDATE {table} SET user_id = 1 WHERE user_id IS NULL")
    if db.fetchall("PRAGMA table_info(notification_log)"):
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_nl_user_sent ON notification_log(user_id, sent_at)"
        )
    if db.fetchall("PRAGMA table_info(notification_queue)"):
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_nq_user_status ON notification_queue(user_id, status)"
        )
