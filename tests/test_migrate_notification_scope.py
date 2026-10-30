"""A-28 通知配置迁移：dry-run / apply / 幂等。"""

import importlib.util
import json
import sqlite3
from pathlib import Path

from pilotstd.core.config.scope import scope_of


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "migrate_notification_scope.py"
    spec = importlib.util.spec_from_file_location("migrate_scope", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _env(tmp_path: Path):
    db = tmp_path / "pilotstd.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE tmp_users (id INTEGER PRIMARY KEY);"
        "ALTER TABLE tmp_users RENAME TO users;"
        "CREATE TABLE tmp_prefs (user_id INTEGER, preference_key TEXT, preference_value TEXT,"
        " PRIMARY KEY(user_id, preference_key));"
        "ALTER TABLE tmp_prefs RENAME TO user_preferences;"
        "INSERT INTO users(id) VALUES (1);"
    )
    conn.commit()
    conn.close()
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "notification.enabled": True,
                "notification.quiet_hours_enabled": True,
                "notification.quiet_hours_start": "23:00",
                "notification.quiet_hours_end": "06:00",
                "notification.rules.scan_complete": ["telegram"],
            }
        ),
        encoding="utf-8",
    )
    return cfg, db


def test_scope_classification():
    assert scope_of("notification.enabled") == "system"
    assert scope_of("notification.callback.token") == "system"
    assert scope_of("notification.channels.telegram.bot_token") == "user"
    assert scope_of("notification.quiet_hours_enabled") == "user"
    assert scope_of("notification.rules.scan_complete") == "user"
    assert scope_of("unknown.key") == "user"


def test_dry_run_writes_nothing(tmp_path: Path):
    mod = _load()
    cfg, db = _env(tmp_path)
    assert mod.main(["--config", str(cfg), "--db", str(db), "--backup-dir", str(tmp_path / "b")]) == 0
    assert "notification.scope_migrated" not in json.loads(cfg.read_text(encoding="utf-8"))
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()[0] == 0
    conn.close()


def test_apply_then_idempotent(tmp_path: Path):
    mod = _load()
    cfg, db = _env(tmp_path)
    assert mod.main(["--config", str(cfg), "--db", str(db), "--backup-dir", str(tmp_path / "b"), "--apply"]) == 0
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["notification.scope_migrated"] is True
    assert data["notification.quiet_hours_enabled"] is True  # 旧键保留
    conn = sqlite3.connect(db)
    value = conn.execute("SELECT preference_value FROM user_preferences").fetchone()[0]
    conn.close()
    assert json.loads(value)["start"] == "23:00"
    assert mod.main(["--config", str(cfg), "--db", str(db), "--apply"]) == 0  # 幂等
