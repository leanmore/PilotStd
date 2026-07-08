# pilotstd/core/db/_migrate_v31_plus.py
# v31-v34 迁移实现，因 migrations.py 超 500 行限制而拆分
from typing import Any


def _migrate_v31_monitor_stats(db: Any) -> None:
    """监控统计从 cache_config 剥离到独立表 monitor_stats。"""
    db.execute(
        "CREATE TABLE IF NOT EXISTS monitor_stats ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, stat_key TEXT NOT NULL,"
        "stat_value INTEGER NOT NULL DEFAULT 0, stat_date TEXT NOT NULL,"
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(stat_key, stat_date))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_monitor_stats_date ON monitor_stats(stat_date)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_monitor_stats_key ON monitor_stats(stat_key)")
    from datetime import date

    today = date.today().isoformat()
    for stat_key in ("processed_today", "success_today", "failed_today"):
        row = db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (f"monitor.{stat_key}",))
        if row:
            try:
                val = int(row["config_value"])
            except (ValueError, TypeError):
                val = 0
            db.execute(
                "INSERT OR REPLACE INTO monitor_stats (stat_key, stat_value, stat_date) VALUES (?, ?, ?)",
                (stat_key.replace("_today", ""), val, today),
            )
    db.execute(
        "DELETE FROM cache_config WHERE config_key IN (?, ?, ?, ?)",
        (
            "monitor.processed_today",
            "monitor.success_today",
            "monitor.failed_today",
            "monitor.last_processed",
        ),
    )


def _migrate_v32_cleanup_dead_tables(db: Any) -> None:
    """删除 announcement_fetch_failures 表（补抓队列功能未启用）。"""
    db.execute("DROP TABLE IF EXISTS announcement_fetch_failures")


def _migrate_rows(db, table, col_map):
    """将旧表行迁移到 adapter_state。col_map: [(src_col, dst_col), ...]"""
    cols = ", ".join(c[1] for c in col_map)
    phs = ", ".join("?" for _ in col_map)
    for row in db.fetchall(f"SELECT * FROM {table}"):
        db.execute(
            f"INSERT OR REPLACE INTO adapter_state ({cols}) VALUES ({phs})",
            [row[c[0]] for c in col_map],
        )


def _migrate_v33_adapter_state(db: Any) -> None:
    """合并 rotator_state + adapter_stats + adapter_health 为 adapter_state。"""
    db.execute(
        "CREATE TABLE IF NOT EXISTS adapter_state ("
        "adapter_name TEXT PRIMARY KEY, request_count INTEGER DEFAULT 0,"
        "daily_count INTEGER DEFAULT 0, daily_date TEXT, cooldown_until REAL DEFAULT 0.0,"
        "consecutive_errors INTEGER DEFAULT 0, active_url TEXT DEFAULT '',"
        "total_queries INTEGER DEFAULT 0, successful_queries INTEGER DEFAULT 0,"
        "avg_response_time REAL DEFAULT 0, total_response_time REAL DEFAULT 0,"
        "cooldown_count INTEGER DEFAULT 0, last_cooldown_reason TEXT, last_cooldown_at TEXT,"
        "freeze_count INTEGER DEFAULT 0, first_freeze_time TEXT, frozen_until TEXT,"
        "fail_streak INTEGER DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    _migrate_rows(
        db,
        "rotator_state",
        [
            ("site_name", "adapter_name"),
            ("request_count", "request_count"),
            ("daily_count", "daily_count"),
            ("daily_date", "daily_date"),
            ("cooldown_until", "cooldown_until"),
            ("consecutive_errors", "consecutive_errors"),
            ("active_url", "active_url"),
            ("updated_at", "updated_at"),
        ],
    )
    _migrate_rows(
        db,
        "adapter_stats",
        [
            ("adapter_name", "adapter_name"),
            ("total_queries", "total_queries"),
            ("successful_queries", "successful_queries"),
            ("avg_response_time", "avg_response_time"),
            ("total_response_time", "total_response_time"),
            ("cooldown_count", "cooldown_count"),
            ("last_cooldown_reason", "last_cooldown_reason"),
            ("last_cooldown_at", "last_cooldown_at"),
            ("last_updated", "updated_at"),
        ],
    )
    _migrate_rows(
        db,
        "adapter_health",
        [
            ("adapter_name", "adapter_name"),
            ("freeze_count", "freeze_count"),
            ("first_freeze_time", "first_freeze_time"),
            ("frozen_until", "frozen_until"),
            ("fail_streak", "fail_streak"),
            ("updated_at", "updated_at"),
        ],
    )


def _migrate_v34_drop_old_adapter_tables(db: Any) -> None:
    """删除合并后被取代的三张旧表。"""
    db.execute("DROP TABLE IF EXISTS rotator_state")
    db.execute("DROP TABLE IF EXISTS adapter_stats")
    db.execute("DROP TABLE IF EXISTS adapter_health")
