import json
import sqlite3
from pathlib import Path

from tests.test_migrate_notification_scope import _env, _load


def test_backup_failure_writes_nothing(tmp_path: Path):
    mod = _load()
    cfg, db = _env(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.write_text("x", encoding="utf-8")
    ret = mod.main(["--config", str(cfg), "--db", str(db), "--backup-dir", str(blocked), "--apply"])
    assert ret == 1
    assert "notification.scope_migrated" not in json.loads(cfg.read_text(encoding="utf-8"))
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()[0] == 0
    conn.close()


def test_midwrite_failure_leaves_no_marker(tmp_path: Path):
    mod = _load()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"notification.quiet_hours_enabled": True}), encoding="utf-8")
    db = tmp_path / "pilotstd.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE tmp_prefs (user_id INTEGER, preference_key TEXT, preference_value TEXT,"
        " PRIMARY KEY(user_id, preference_key));"
        "ALTER TABLE tmp_prefs RENAME TO user_preferences;"
    )
    conn.commit()
    conn.close()
    ret = mod.main(["--config", str(cfg), "--db", str(db), "--backup-dir", str(tmp_path / "b"), "--apply"])
    assert ret == 1
    assert "notification.scope_migrated" not in json.loads(cfg.read_text(encoding="utf-8"))


def test_bad_config_returns_failure(tmp_path: Path):
    mod = _load()
    cfg, db = _env(tmp_path)
    cfg.write_text("{not json", encoding="utf-8")
    assert mod.main(["--config", str(cfg), "--db", str(db), "--apply"]) == 1


def test_reset_keeps_data_and_allows_force(tmp_path: Path):
    mod = _load()
    cfg, db = _env(tmp_path)
    base = ["--config", str(cfg), "--db", str(db), "--backup-dir", str(tmp_path / "b")]
    assert mod.main(base + ["--apply"]) == 0
    assert mod.main(base + ["--reset"]) == 0
    assert "notification.scope_migrated" not in json.loads(cfg.read_text(encoding="utf-8"))
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()[0] == 1
    conn.close()
    assert mod.main(base + ["--apply", "--force"]) == 0

def test_rollback_exports_all_notification_prefs_and_deletes_migrated(tmp_path: Path):
    mod = _load()
    cfg, db = _env(tmp_path)
    base = ["--config", str(cfg), "--db", str(db), "--backup-dir", str(tmp_path / "b")]
    assert mod.main(base + ["--apply"]) == 0
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO user_preferences(user_id, preference_key, preference_value) VALUES(1,?,?)",
        ("notification.enabled", "true"),
    )
    conn.commit()
    conn.close()
    assert mod.main(base + ["--rollback"]) == 0
    exported = list((tmp_path / "b").glob("a28_rollback_*/preferences.json"))
    assert exported and "notification.enabled" in exported[0].read_text(encoding="utf-8")
    conn = sqlite3.connect(db)
    keys = {r[0] for r in conn.execute("SELECT preference_key FROM user_preferences")}
    conn.close()
    assert "notification_quiet_hours" not in keys
    assert "notification.enabled" in keys
    assert "notification.scope_migrated" not in json.loads(cfg.read_text(encoding="utf-8"))
