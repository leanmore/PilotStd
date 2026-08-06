# tests/test_migrate_preferences.py
# Migration script tests — dry-run / idempotent / full migration

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def temp_db():
    """Create a temp SQLite DB with the three old tables and test data."""
    import sqlite3

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.row_factory = sqlite3.Row

    # user_layouts
    conn.execute("""CREATE TABLE user_layouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        layout_key TEXT NOT NULL DEFAULT 'dashboard', layout_data TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, layout_key))""")
    conn.execute(
        "INSERT INTO user_layouts (user_id, layout_key, layout_data) VALUES (1, 'dashboard', ?)",
        (json.dumps([{"i": "stats", "x": 0, "y": 0, "w": 4, "h": 6}]),),
    )
    conn.execute(
        "INSERT INTO user_layouts (user_id, layout_key, layout_data) VALUES (1, 'search', ?)",
        (json.dumps([{"i": "bar", "x": 0, "y": 0, "w": 12, "h": 2}]),),
    )

    # user_settings
    conn.execute("""CREATE TABLE user_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        settings JSON NOT NULL DEFAULT '{}',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute(
        "INSERT INTO user_settings (user_id, settings) VALUES (1, ?)",
        (json.dumps({"ui": {"theme": "dark"}, "notifications": {"enabled": True}}),),
    )

    # user_preferences (existing record)
    conn.execute("""CREATE TABLE user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        preference_key TEXT NOT NULL, preference_value TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, preference_key))""")
    conn.execute(
        "INSERT INTO user_preferences (user_id, preference_key, preference_value)"
        " VALUES (1, 'existing_key', 'existing_value')",
    )
    conn.execute("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO _schema_version (version) VALUES (99)")

    conn.commit()
    conn.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except PermissionError:
        pass


from unittest.mock import patch


class TestMigratePreferences:

    def test_dry_run_no_writes(self, temp_db):
        with patch("scripts.migrate_preferences.get_db_path", return_value=temp_db):
            from scripts.migrate_preferences import migrate
            stats = migrate(dry_run=True)

        assert stats["layout_rows"] == 2
        assert stats["layout_migrated"] == 2
        assert stats["settings_rows"] == 1
        assert stats["settings_migrated"] == 2
        assert stats["existing_prefs"] == 1

        # Verify no writes
        import sqlite3
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cnt = conn.execute("SELECT COUNT(*) as c FROM user_preferences").fetchone()["c"]
        assert cnt == 1
        conn.close()

    def test_full_migration(self, temp_db):
        with patch("scripts.migrate_preferences.get_db_path", return_value=temp_db):
            from scripts.migrate_preferences import migrate
            stats = migrate(dry_run=False)

        assert stats["layout_migrated"] == 2
        assert stats["settings_migrated"] == 2

        import sqlite3
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT preference_key FROM user_preferences WHERE user_id=1 ORDER BY preference_key"
        ).fetchall()
        keys = {r["preference_key"] for r in rows}
        assert "existing_key" in keys
        assert "layout:dashboard" in keys
        assert "layout:search" in keys
        assert "settings:ui" in keys
        assert "settings:notifications" in keys
        conn.close()

    def test_idempotent_repeat(self, temp_db):
        with patch("scripts.migrate_preferences.get_db_path", return_value=temp_db):
            from scripts.migrate_preferences import migrate
            stats1 = migrate(dry_run=False)
            stats2 = migrate(dry_run=False)

        assert stats1["layout_migrated"] == 2
        assert stats1["settings_migrated"] == 2
        assert stats2["layout_migrated"] == 0
        assert stats2["settings_migrated"] == 0
