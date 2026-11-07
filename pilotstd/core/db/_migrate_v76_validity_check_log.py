"""v76：新增 validity_check_log，保存每次时效性检查的查询结果/失败原因。"""

from __future__ import annotations

from typing import Any

from ._constants import migration


@migration(76)
def _migrate_v76_validity_check_log(db: Any) -> None:
    # 检查病历：状态之外，保留“这次查到了什么”，供回看和通知失败排查。
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS validity_check_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            previous_status TEXT,
            found_name TEXT NOT NULL DEFAULT '',
            source_site TEXT NOT NULL DEFAULT '',
            match_status TEXT NOT NULL DEFAULT '',
            ok INTEGER NOT NULL DEFAULT 1,
            error TEXT NOT NULL DEFAULT '',
            result_json TEXT NOT NULL DEFAULT ''
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_validity_check_std "
        "ON validity_check_log(standard_number, checked_at)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_validity_check_time "
        "ON validity_check_log(checked_at)"
    )
