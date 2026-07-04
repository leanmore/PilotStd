# pilotstd/core/db/migrations.py
# Schema 迁移函数（v2-v27）— 从 db.py 拆分

import logging
from typing import Any

from ._constants import migration


@migration(2)
def _migrate_v2_add_file_index(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS file_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT NOT NULL UNIQUE,
        logical_code TEXT NOT NULL DEFAULT '', number INTEGER NOT NULL DEFAULT 0,
        year INTEGER NOT NULL DEFAULT 0, part INTEGER NOT NULL DEFAULT -1,
        std_name TEXT NOT NULL DEFAULT '', file_hash TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '现行', scanned_at TEXT NOT NULL DEFAULT '')""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_file_index_hash ON file_index(file_hash)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_file_index_code ON file_index(logical_code, number)")


@migration(3)
def _migrate_v3_queue_and_pending(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS download_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT NOT NULL,
        standard_name TEXT NOT NULL DEFAULT '', publish_date TEXT NOT NULL DEFAULT '',
        expected_available TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT '',
        retry_count INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'waiting')""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_download_queue_status ON download_queue(status)")
    db.execute("""CREATE TABLE IF NOT EXISTS pending_lookup (
        id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT NOT NULL,
        std_name TEXT NOT NULL DEFAULT '', found_name TEXT NOT NULL DEFAULT '',
        found_number TEXT NOT NULL DEFAULT '', match_status TEXT NOT NULL DEFAULT '',
        effect_status TEXT NOT NULL DEFAULT '', score INTEGER NOT NULL DEFAULT 0,
        source_site TEXT NOT NULL DEFAULT '', file_path TEXT NOT NULL DEFAULT '',
        source_name TEXT NOT NULL DEFAULT '', final_name TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT '', resolved_at TEXT NOT NULL DEFAULT '')""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_pending_lookup_status ON pending_lookup(status)")
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(file_index)")}
    if "status" not in cols:
        db.execute("ALTER TABLE file_index ADD COLUMN status TEXT NOT NULL DEFAULT '现行'")


@migration(4)
def _migrate_v4_add_fetch_checkpoint(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS fetch_checkpoint (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_site TEXT NOT NULL UNIQUE,
        last_fetched_at TEXT NOT NULL DEFAULT '', last_notice_date TEXT NOT NULL DEFAULT '')""")


@migration(5)
def _migrate_v5_announcement_match(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS announcement_match (
        id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT NOT NULL,
        source_site TEXT NOT NULL DEFAULT 'announcement', result_json TEXT NOT NULL,
        cached_at TEXT NOT NULL, expires_at TEXT)""")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_announcement_match_lookup "
        "ON announcement_match(standard_number, source_site)"
    )


@migration(6)
def _migrate_v6_add_rotator_state(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS rotator_state (
        site_name TEXT PRIMARY KEY, request_count INTEGER NOT NULL DEFAULT 0,
        daily_count INTEGER NOT NULL DEFAULT 0, daily_date TEXT NOT NULL DEFAULT '',
        cooldown_until REAL NOT NULL DEFAULT 0.0, consecutive_errors INTEGER NOT NULL DEFAULT 0,
        active_url TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")


@migration(7)
def _migrate_v7_add_last_checked(db: Any) -> None:
    try:
        db.execute("ALTER TABLE file_index ADD COLUMN last_checked TEXT")
    except Exception:
        logging.getLogger("pilotstd.db").debug("v7 迁移：last_checked 列可能已存在", exc_info=True)
    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_file_index_last_checked ON file_index(last_checked)")
    except Exception:
        logging.getLogger("pilotstd.db").debug("v7 迁移：file_index 表不存在，跳过索引创建", exc_info=True)


@migration(8)
def _migrate_v8_drop_expires_at(db: Any) -> None:
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    if not cols:
        logging.getLogger("pilotstd.db").debug("v8 迁移：standard_info_cache 表不存在，跳过")
        return
    if "expires_at" in cols:
        db.execute("ALTER TABLE standard_info_cache DROP COLUMN expires_at")


@migration(9)
def _migrate_v9_add_requery_count(db: Any) -> None:
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(pending_lookup)")}
    if not cols:
        return
    if "requery_count" not in cols:
        db.execute("ALTER TABLE pending_lookup ADD COLUMN requery_count INTEGER DEFAULT 0")


@migration(10)
def _migrate_v10_add_source_and_status_history(db: Any) -> None:
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    if not cols:
        return
    if "source" not in cols:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN source TEXT NOT NULL DEFAULT 'network'")
    if "status_history" not in cols:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN status_history TEXT NOT NULL DEFAULT ''")


@migration(11)
def _migrate_v11_add_daily_limits(db: Any) -> None:
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(rotator_state)")}
    if not cols:
        return
    if "daily_count" not in cols:
        db.execute("ALTER TABLE rotator_state ADD COLUMN daily_count INTEGER NOT NULL DEFAULT 0")
    if "daily_date" not in cols:
        db.execute("ALTER TABLE rotator_state ADD COLUMN daily_date TEXT NOT NULL DEFAULT ''")


@migration(12)
def _migrate_v12_adapter_stats(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS adapter_stats (
        adapter_name TEXT PRIMARY KEY, total_queries INTEGER DEFAULT 0,
        successful_queries INTEGER DEFAULT 0,
        last_updated TEXT DEFAULT (datetime('now', 'localtime')))""")


@migration(13)
def _migrate_v13_adapter_stats_extend(db: Any) -> None:
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(adapter_stats)")}
    if not cols:
        return
    for col_name, col_type in [
        ("avg_response_time", "REAL DEFAULT 0"),
        ("total_response_time", "REAL DEFAULT 0"),
        ("cooldown_count", "INTEGER DEFAULT 0"),
        ("last_cooldown_reason", "TEXT"),
        ("last_cooldown_at", "TEXT"),
    ]:
        if col_name not in cols:
            db.execute(f"ALTER TABLE adapter_stats ADD COLUMN {col_name} {col_type}")


@migration(14)
def _migrate_v14_api_keys(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT, key_id TEXT NOT NULL UNIQUE,
        key_hash TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '',
        scopes TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        expires_at TEXT, last_used_at TEXT, is_active INTEGER NOT NULL DEFAULT 1,
        created_by TEXT NOT NULL DEFAULT '')""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active)")


@migration(15)
def _migrate_v15_announcement_record(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS announcement_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_site TEXT NOT NULL, pid TEXT NOT NULL,
        announce_no TEXT, standard_number TEXT NOT NULL, std_name TEXT, publish_date TEXT,
        fetched_at TEXT NOT NULL, matched INTEGER DEFAULT 0,
        UNIQUE(source_site, pid, standard_number))""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_pid ON announcement_record(source_site, pid)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_standard ON announcement_record(standard_number)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_matched ON announcement_record(matched)")


@migration(16)
def _migrate_v16_validity_status(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS standard_validity (
        id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT '未知', last_checked_at TEXT, next_check_at TEXT,
        last_status TEXT, last_status_updated_at TEXT, check_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_validity_next_check ON standard_validity(next_check_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_validity_standard ON standard_validity(standard_number)")


@migration(17)
def _migrate_v17_notification_log(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS notification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
        channel TEXT NOT NULL, title TEXT, body TEXT, standard_number TEXT,
        status TEXT NOT NULL DEFAULT 'success', error_msg TEXT,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_sent_at ON notification_log(sent_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_event_type ON notification_log(event_type)")


@migration(18)
def _migrate_v18_notification_fetch_task(db: Any) -> None:
    """v18: 通知日志 is_read 列 + 异步抓取任务表 + 适配器熔断健康表（合并重复 v18）。"""
    db.execute("ALTER TABLE notification_log ADD COLUMN is_read INTEGER DEFAULT 0")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_is_read ON notification_log(is_read)")
    db.execute("""CREATE TABLE IF NOT EXISTS fetch_task (
        id TEXT PRIMARY KEY, task_type TEXT DEFAULT 'announcement',
        status TEXT DEFAULT 'pending', progress INTEGER DEFAULT 0, result_data TEXT,
        error_msg TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS adapter_health (
        adapter_name TEXT PRIMARY KEY, freeze_count INTEGER DEFAULT 0,
        first_freeze_time TIMESTAMP, frozen_until TIMESTAMP, fail_streak INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")


@migration(19)
def _migrate_v19_users(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
        must_change_password INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(users)")}
    if "role" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "must_change_password" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")


@migration(20)
def _migrate_v20_register_runtime_tables(db: Any) -> None:
    for tbl in ("daily_quota", "task_queue", "scheduler_lock"):
        exists = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
        if not exists:
            pass


@migration(21)
def _migrate_v21_user_layouts(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS user_layouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        layout_key TEXT NOT NULL DEFAULT 'dashboard', layout_data TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, layout_key))""")


@migration(22)
def _migrate_v22_user_preferences(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        preference_key TEXT NOT NULL, preference_value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, preference_key))""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_preferences_user_key ON user_preferences(user_id, preference_key)")


@migration(23)
def _migrate_v23_cache_system(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS data_source_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL UNIQUE,
        version TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for src in ("file_index", "announcement", "validity"):
        db.execute("INSERT OR IGNORE INTO data_source_versions (source_name, version) VALUES (?, 'initial')", (src,))
    db.execute("""CREATE TABLE IF NOT EXISTS cache_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT, config_key TEXT NOT NULL UNIQUE,
        config_value TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for ck, cv in (("max_size_mb", "50"), ("auto_cleanup", "true"), ("cleanup_ratio", "0.1")):
        db.execute("INSERT OR IGNORE INTO cache_config (config_key, config_value) VALUES (?, ?)", (ck, cv))
    for table in ("standard_info_cache", "standard_validity", "announcement_record"):
        existing = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not existing:
            if table == "standard_info_cache":
                db.execute("""CREATE TABLE IF NOT EXISTS standard_info_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT NOT NULL,
                    source_site TEXT NOT NULL, result_json TEXT NOT NULL, cached_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'network',
                    status_history TEXT NOT NULL DEFAULT '')""")
            elif table == "standard_validity":
                db.execute("""CREATE TABLE IF NOT EXISTS standard_validity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    standard_number TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT '未知',
                    last_checked_at TEXT, next_check_at TEXT, last_status TEXT,
                    last_status_updated_at TEXT, check_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            elif table == "announcement_record":
                db.execute("""CREATE TABLE IF NOT EXISTS announcement_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, source_site TEXT NOT NULL,
                    pid TEXT NOT NULL, announce_no TEXT, standard_number TEXT NOT NULL,
                    std_name TEXT, publish_date TEXT, fetched_at TEXT NOT NULL,
                    matched INTEGER DEFAULT 0,
                    UNIQUE(source_site, pid, standard_number))""")
        cols = {r["name"] for r in db.fetchall(f"PRAGMA table_info({table})")}
        if "source_version" not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN source_version TEXT DEFAULT ''")
        if "data_state" not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN data_state TEXT DEFAULT 'valid'")
        if "last_accessed_at" not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN last_accessed_at TEXT DEFAULT NULL")


@migration(24)
def _migrate_v24_task_queue_enhance(db: Any) -> None:
    existing = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='task_queue'")
    if not existing:
        db.execute("""CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL UNIQUE,
            task_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            total_items INTEGER DEFAULT 0, completed_items INTEGER DEFAULT 0,
            failed_items INTEGER DEFAULT 0, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, result_json TEXT DEFAULT '',
            error_log TEXT DEFAULT '')""")
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(task_queue)")}
    for col_name, col_def in [
        ("retry_count", "INTEGER DEFAULT 0"),
        ("max_retries", "INTEGER DEFAULT 3"),
        ("timeout_seconds", "INTEGER DEFAULT 300"),
        ("started_at", "TEXT"),
        ("finished_at", "TEXT"),
        ("priority", "INTEGER DEFAULT 0"),
        ("queue_name", "TEXT DEFAULT 'default'"),
    ]:
        if col_name not in cols:
            db.execute(f"ALTER TABLE task_queue ADD COLUMN {col_name} {col_def}")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_status_priority ON task_queue(status, priority, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_queue_name ON task_queue(queue_name)")


@migration(25)
def _migrate_v25_announcement_match_safeguard(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS announcement_match (
        id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT NOT NULL,
        source_site TEXT NOT NULL DEFAULT 'announcement', result_json TEXT NOT NULL,
        cached_at TEXT NOT NULL, expires_at TEXT)""")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_announcement_match_lookup "
        "ON announcement_match(standard_number, source_site)"
    )


@migration(26)
def _migrate_v26_pipeline_runs(db: Any) -> None:
    """用户触发的管道执行追踪表。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL UNIQUE,
            current_step TEXT NOT NULL DEFAULT 'scan',
            status TEXT NOT NULL DEFAULT 'running',
            progress INTEGER DEFAULT 0,
            step_results TEXT DEFAULT '{}',
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id ON pipeline_runs(run_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status)")


@migration(27)
def _migrate_v27_notification_aggregation(db: Any) -> None:
    """通知日志增加聚合字段（幂等检查）。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(notification_log)")}
    if "aggregated_count" not in cols:
        db.execute("ALTER TABLE notification_log ADD COLUMN aggregated_count INTEGER DEFAULT 1")
    if "link" not in cols:
        db.execute("ALTER TABLE notification_log ADD COLUMN link TEXT")
    if "icon" not in cols:
        db.execute("ALTER TABLE notification_log ADD COLUMN icon TEXT")


@migration(28)
def _migrate_v28_notification_queue(db: Any) -> None:
    """通知静音暂存队列表。"""
    db.execute("""CREATE TABLE IF NOT EXISTS notification_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
        event_data TEXT NOT NULL, status TEXT DEFAULT 'pending',
        scheduled_time TEXT, error_msg TEXT DEFAULT '',
        created_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_nq_status ON notification_queue(status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_nq_scheduled ON notification_queue(scheduled_time)")
