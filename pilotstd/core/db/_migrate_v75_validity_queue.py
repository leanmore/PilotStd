# 模块：迁移 v75 — 建立时效性检查队列
"""v75：补建 `validity_check_queue`，让“检查选中文件”不再是假成功。

背景（2026-11-07）：
- 前端 OrganizeView 调用 `/api/validity/enqueue`；
- ValidityService 写 `validity_check_queue`；
- 但该表从未建过，异常被逐条吞掉，接口返回 ok=True / enqueued=0。
"""

from __future__ import annotations

from typing import Any

from ._constants import migration

_TABLE = "validity_check_queue"


@migration(75)
def _migrate_v75_validity_queue(db: Any) -> None:
    """幂等建表；队列行按“文件路径 + 状态”去重，允许失败后重试。"""
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_validity_queue_status "
        f"ON {_TABLE}(status, id)"
    )
    db.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_validity_queue_pending_unique "
        f"ON {_TABLE}(file_path) WHERE status='pending'"
    )
