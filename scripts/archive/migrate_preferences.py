#!/usr/bin/env python3
"""
scripts/migrate_preferences.py — 三表合一迁移脚本

将 user_layouts 和 user_settings 的数据迁移到统一的 user_preferences 表。
user_preferences 中已有数据保持不变。

迁移映射规则:
  user_layouts → preference_key = 'layout:{layout_key}'   (如 layout:dashboard)
  user_settings → preference_key = 'settings:{json_key}'    (如 settings:ui)
  user_preferences（已有）→ key 不变

使用方式:
  python scripts/migrate_preferences.py --dry-run    # 预览
  python scripts/migrate_preferences.py              # 执行迁移
  python scripts/migrate_preferences.py              # 重复执行（幂等，无副作用）

SQLite 限制：不支持 COMMENT ON TABLE。旧表标记为 DEPRECATED 的方式：
  - 迁移脚本运行后打印警告提示
  - 在 migrations.py 注释中标注 deprecated
  - 旧表保留不删除（回滚能力）
"""

import argparse
import json
import os
import sys
from typing import Any

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

from pilotstd.core.config.paths import get_db_path

# 迁移日志前缀
PREFIX = "[migrate_preferences]"


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a sqlite3 connection with dict-like row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check whether a table exists in the database."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check whether a column exists in the given table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _count_table(conn: sqlite3.Connection, table: str) -> int:
    """Return the row count of a table, or 0 if it does not exist."""
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
    return row["cnt"] if row else 0


def _get_existing_keys(conn: sqlite3.Connection, user_id: int) -> set[str]:
    """Return the set of preference_key values for a user, or empty set."""
    if not _table_exists(conn, "user_preferences"):
        return set()
    if not _column_exists(conn, "user_preferences", "preference_key"):
        return set()
    rows = conn.execute(
        "SELECT preference_key FROM user_preferences WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {r["preference_key"] for r in rows}


def migrate(dry_run: bool = False) -> dict[str, Any]:
    """Run the migration. Returns a stats dict with counts."""
    conn = _connect(get_db_path())
    stats: dict[str, Any] = {
        "layout_rows": 0,
        "layout_migrated": 0,
        "layout_skipped": 0,
        "settings_rows": 0,
        "settings_migrated": 0,
        "settings_skipped": 0,
        "existing_prefs": 0,
    }

    # 1. 统计现有 user_preferences 记录数
    stats["existing_prefs"] = _count_table(conn, "user_preferences")

    # 2. 迁移 user_layouts → user_preferences
    layouts: list[sqlite3.Row] = []
    if _table_exists(conn, "user_layouts"):
        layouts = conn.execute(
            "SELECT user_id, layout_key, layout_data FROM user_layouts"
        ).fetchall()
    stats["layout_rows"] = len(layouts)

    for row in layouts:
        pref_key = f"layout:{row['layout_key']}"
        user_id = row["user_id"]
        existing_keys = _get_existing_keys(conn, user_id)

        if pref_key in existing_keys:
            stats["layout_skipped"] += 1
            print(f"{PREFIX} {'[DRY-RUN] ' if dry_run else ''}skip existing: user_id={user_id}, key={pref_key}")
            continue

        stats["layout_migrated"] += 1
        if dry_run:
            print(f"{PREFIX} [DRY-RUN] would insert: user_id={user_id}, key={pref_key}")
        else:
            conn.execute(
                "INSERT INTO user_preferences (user_id, preference_key, preference_value, updated_at)"
                " VALUES (?, ?, ?, datetime('now', 'localtime'))",
                (user_id, pref_key, row["layout_data"]),
            )
            conn.commit()

    # 3. 迁移 user_settings → user_preferences
    settings_rows: list[sqlite3.Row] = []
    if _table_exists(conn, "user_settings"):
        settings_rows = conn.execute(
            "SELECT user_id, settings FROM user_settings"
        ).fetchall()
    stats["settings_rows"] = len(settings_rows)

    for row in settings_rows:
        user_id = row["user_id"]
        try:
            parsed = json.loads(row["settings"])
        except (json.JSONDecodeError, TypeError):
            print(f"{PREFIX} [WARN] user_id={user_id} settings JSON parse failed, skip")
            continue

        if not isinstance(parsed, dict):
            print(f"{PREFIX} [WARN] user_id={user_id} settings is not dict, skip")
            continue

        existing_keys = _get_existing_keys(conn, user_id)

        for key, value in parsed.items():
            pref_key = f"settings:{key}"
            value_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

            if pref_key in existing_keys:
                stats["settings_skipped"] += 1
                print(f"{PREFIX} {'[DRY-RUN] ' if dry_run else ''}skip existing: user_id={user_id}, key={pref_key}")
                continue

            stats["settings_migrated"] += 1
            if dry_run:
                print(f"{PREFIX} [DRY-RUN] would insert: user_id={user_id}, key={pref_key}")
            else:
                conn.execute(
                    "INSERT INTO user_preferences (user_id, preference_key, preference_value, updated_at)"
                    " VALUES (?, ?, ?, datetime('now', 'localtime'))",
                    (user_id, pref_key, value_str),
                )
                conn.commit()

    conn.close()
    return stats


def print_summary(stats: dict[str, Any], dry_run: bool) -> None:
    """Print migration result summary to stdout."""
    mode = "DRY-RUN" if dry_run else "Completed"
    print(f"\n{'=' * 60}")
    print(f"  {PREFIX} {mode}")
    print(f"{'=' * 60}")
    print(f"  Existing user_preferences:   {stats['existing_prefs']}")
    print(f"  user_layouts source rows:     {stats['layout_rows']}")
    print(f"    -> migrated:                {stats['layout_migrated']}")
    print(f"    -> skipped:                 {stats['layout_skipped']}")
    print(f"  user_settings source rows:    {stats['settings_rows']}")
    print(f"    -> migrated:                {stats['settings_migrated']}")
    print(f"    -> skipped:                 {stats['settings_skipped']}")
    print(f"{'=' * 60}")
    total = stats["layout_migrated"] + stats["settings_migrated"]
    if dry_run:
        print(f"  Planned inserts: {total} (not written)")
    else:
        print(f"  Total written: {total}")
    print(f"{'=' * 60}")

    if not dry_run and (stats["layout_rows"] > 0 or stats["settings_rows"] > 0):
        print("\n  Data from old tables migrated to user_preferences.")
        print("  Old tables preserved for rollback. After verification, drop manually:")
        print("    DROP TABLE IF EXISTS user_layouts;")
        print("    DROP TABLE IF EXISTS user_settings;")
        print()


def main() -> None:
    """Entry point: parse args, run migration, print summary."""
    parser = argparse.ArgumentParser(description="Merge user_layouts + user_settings into user_preferences")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode: show planned inserts without writing",
    )
    args = parser.parse_args()

    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"{PREFIX} Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"{PREFIX} Database: {db_path}")
    stats = migrate(dry_run=args.dry_run)
    print_summary(stats, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
