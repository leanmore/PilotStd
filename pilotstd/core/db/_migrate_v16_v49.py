# 模块：项目/核心/数据库/迁移_v16_v49脚本
# v16~v49 内联迁移从 migrations.py 拆出，避免 G-010 单文件超限
# 注意：函数体与装饰器逐字符保留，保证迁移 checksum 与生产库一致

import logging
from typing import Any

from ._constants import migration

@migration(16)
def _migrate_v16_standard_validity(db: Any) -> None:
    """创建 standard_validity 表，记录标准号的有效性状态及检查周期。"""
    db.execute("""CREATE TABLE IF NOT EXISTS standard_validity (
        id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT '未知', last_checked_at TEXT, next_check_at TEXT,
        last_status TEXT, last_status_updated_at TEXT, check_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_validity_next_check ON standard_validity(next_check_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_validity_standard ON standard_validity(standard_number)")



@migration(17)
def _migrate_v17_notification_log(db: Any) -> None:
    """创建 notification_log 表，记录通知发送的事件类型、渠道和结果。"""
    db.execute("""CREATE TABLE IF NOT EXISTS notification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
        channel TEXT NOT NULL, title TEXT, body TEXT, standard_number TEXT,
        status TEXT NOT NULL DEFAULT 'success', error_msg TEXT,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_sent_at ON notification_log(sent_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_event_type ON notification_log(event_type)")



@migration(18)
def _migrate_v18_notification_fetch_task(db: Any) -> None:
    """创建 fetch_task 和 adapter_health 表，通知日志新增已读标记。"""
    try:
        db.execute("ALTER TABLE notification_log ADD COLUMN is_read INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_notif_is_read ON notification_log(is_read)")
    except Exception:
        pass
    db.execute("""CREATE TABLE IF NOT EXISTS fetch_task (
        id TEXT PRIMARY KEY, task_type TEXT DEFAULT 'announcement', status TEXT DEFAULT 'pending',
        progress INTEGER DEFAULT 0, result_data TEXT,
        error_msg TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS adapter_health (
        adapter_name TEXT PRIMARY KEY, freeze_count INTEGER DEFAULT 0,
        first_freeze_time TIMESTAMP, frozen_until TIMESTAMP, fail_streak INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")



@migration(19)
def _migrate_v19_users(db: Any) -> None:
    """创建 users 表，存储用户名、密码哈希、盐值和角色。"""
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
        must_change_password INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")



@migration(20)
def _migrate_v20_announce_since_date(db: Any) -> None:
    try:
        db.execute("ALTER TABLE fetch_checkpoint ADD COLUMN since_date_override TEXT DEFAULT ''")
    except Exception:
        pass



@migration(21)
def _migrate_v21_user_layouts(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS user_layouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        layout_key TEXT NOT NULL DEFAULT 'dashboard', layout_data TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, layout_key))""")



@migration(22)
def _migrate_v22_user_preferences(db: Any) -> None:
    """创建 user_preferences 表，以 KV 形式存储用户偏好设置。"""
    db.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        preference_key TEXT NOT NULL, preference_value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, preference_key))""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_preferences_user_key ON user_preferences(user_id, preference_key)")



@migration(23)
def _migrate_v23_cache_system(db: Any) -> None:
    """初始化缓存系统：数据源版本表 + 缓存配置表 + 多表缓存元数据字段扩展。"""
    db.execute("""CREATE TABLE IF NOT EXISTS data_source_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL UNIQUE,
        version TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for src in ("file_index", "announcement", "validity"):
        db.execute("INSERT OR IGNORE INTO data_source_versions (source_name, version) VALUES (?, 'initial')", (src,))
    db.execute("""CREATE TABLE IF NOT EXISTS cache_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT, config_key TEXT NOT NULL UNIQUE,
        config_value TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    for key, val in [("max_size_mb", "50"), ("auto_cleanup", "true"), ("cleanup_ratio", "0.1")]:
        db.execute("INSERT OR IGNORE INTO cache_config (config_key, config_value) VALUES (?, ?)", (key, val))
    try:
        db.execute("ALTER TABLE standard_validity ADD COLUMN source_version TEXT DEFAULT 'initial'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE standard_validity ADD COLUMN data_state TEXT DEFAULT 'fresh'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE standard_validity ADD COLUMN last_accessed_at TEXT")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN source_version TEXT DEFAULT 'initial'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN data_state TEXT DEFAULT 'fresh'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN last_accessed_at TEXT")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE announcement_match ADD COLUMN source_version TEXT DEFAULT 'initial'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE announcement_match ADD COLUMN data_state TEXT DEFAULT 'fresh'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE announcement_match ADD COLUMN last_accessed_at TEXT")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE announcement_record ADD COLUMN source_version TEXT DEFAULT 'initial'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE announcement_record ADD COLUMN data_state TEXT DEFAULT 'fresh'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE announcement_record ADD COLUMN last_accessed_at TEXT")
    except Exception:
        pass



@migration(24)
def _migrate_v24_task_queue(db: Any) -> None:
    """创建通用 task_queue 表，支持优先级、重试、超时和队列分组。"""
    db.execute("""CREATE TABLE IF NOT EXISTS task_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL UNIQUE,
        task_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        total_items INTEGER DEFAULT 0, completed_items INTEGER DEFAULT 0,
        failed_items INTEGER DEFAULT 0, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, result_json TEXT DEFAULT '', error_log TEXT DEFAULT '')""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_updated ON task_queue(updated_at)")
    for col_name, col_type in [
        ("retry_count", "INTEGER DEFAULT 0"),
        ("max_retries", "INTEGER DEFAULT 3"),
        ("timeout_seconds", "INTEGER DEFAULT 3600"),
        ("started_at", "TEXT"),
        ("finished_at", "TEXT"),
        ("priority", "INTEGER DEFAULT 0"),
        ("queue_name", "TEXT DEFAULT 'default'"),
    ]:
        try:
            db.execute(f"ALTER TABLE task_queue ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_status_created ON task_queue(status, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_status_priority ON task_queue(status, priority, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_queue_name ON task_queue(queue_name)")



@migration(25)
def _migrate_v25_announcement_match_cache(db: Any) -> None:
    """announcement_match 表新增 source 和 status_history 列。"""
    try:
        db.execute("ALTER TABLE announcement_match ADD COLUMN source TEXT NOT NULL DEFAULT 'announcement'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE announcement_match ADD COLUMN status_history TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass



@migration(26)
def _migrate_v26_pipeline_runs(db: Any) -> None:
    """创建 pipeline_runs 表，记录流水线执行的运行状态和步骤结果。"""
    db.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE,
        current_step TEXT NOT NULL DEFAULT 'scan', status TEXT NOT NULL DEFAULT 'running',
        progress INTEGER DEFAULT 0, step_results TEXT DEFAULT '{}',
        error_message TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id ON pipeline_runs(run_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status)")



@migration(27)
def _migrate_v27_notification_aggregation(db: Any) -> None:
    """notification_log 表新增聚合计数、链接和图标字段。"""
    try:
        db.execute("ALTER TABLE notification_log ADD COLUMN aggregated_count INTEGER DEFAULT 1")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE notification_log ADD COLUMN link TEXT")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE notification_log ADD COLUMN icon TEXT")
    except Exception:
        pass



@migration(28)
def _migrate_v28_notification_queue(db: Any) -> None:
    """创建 notification_queue 表，支持通知的异步调度发送。"""
    db.execute("""CREATE TABLE IF NOT EXISTS notification_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
        event_data TEXT NOT NULL, status TEXT DEFAULT 'pending',
        scheduled_time TEXT, error_msg TEXT DEFAULT '', created_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_nq_status ON notification_queue(status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_nq_scheduled ON notification_queue(scheduled_time)")



@migration(29)
def _migrate_v29_announce_title_and_count(db: Any) -> None:
    """announcement_record 表新增公告标题和标准总数字段。"""
    try:
        db.execute("ALTER TABLE announcement_record ADD COLUMN announcement_title TEXT")
    except Exception:
        pass  # 列已存在
    try:
        db.execute("ALTER TABLE announcement_record ADD COLUMN standard_count INTEGER")
    except Exception:
        pass  # 列已存在



@migration(30)
def _migrate_v30_failure_tables(db: Any) -> None:
    """公告抓取失败记录 + 补抓队列 + 并发锁 + 用户偏好。"""
    db.execute(
        """CREATE TABLE IF NOT EXISTS fetch_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            source_site TEXT NOT NULL,
            since_date TEXT NOT NULL,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TEXT,
            resolved BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS announcement_fetch_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL,
            publish_date TEXT,
            source_site TEXT NOT NULL,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TEXT,
            resolved BOOLEAN DEFAULT FALSE,
            task_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES fetch_failures(id)
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS fetch_locks (
            lock_key TEXT PRIMARY KEY,
            locked_at TEXT,
            locked_by TEXT
        )"""
    )

    # 4._—独立全局配置表（不动22创建的_）
    db.execute(
        """CREATE TABLE IF NOT EXISTS app_preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("INSERT OR IGNORE INTO app_preferences (key, value) VALUES ('announce_since_date', '')")



@migration(38)
def _migrate_v38_user_settings(db) -> None:
    """新增 user_settings 表（JSON 聚合存储），与现有 user_preferences（KV 存储）并存。"""
    logger = logging.getLogger(__name__)

    # 防御性检查：查询数据库_确认表是否已存在
    result = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
    if result:
        logger.info("user_settings 表已存在，跳过创建")
        return

    db.execute("""
        CREATE TABLE user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            settings JSON NOT NULL DEFAULT '{}',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    db.execute("CREATE INDEX idx_user_settings_user_id ON user_settings(user_id)")

    logger.info("user_settings 表创建完成")



@migration(41)
def _migrate_v41_file_index_raw_number(db: Any) -> None:
    try:
        db.execute("ALTER TABLE file_index ADD COLUMN raw_number TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass  # 列已存在



@migration(42)
def _migrate_v42_create_standards_table(db: Any) -> None:
    """Q6-0: 创建 standards 表 — 标准归档四要素精确匹配表。
    sha256 使用 hash_file_content() 混合哈希，非标准 SHA-256。
    """
    db.execute("""
        CREATE TABLE IF NOT EXISTS standards (
            id          INTEGER  PRIMARY KEY AUTOINCREMENT,
            sha256      TEXT     NOT NULL,
            code        TEXT     NOT NULL,
            name        TEXT     NOT NULL,
            size        INTEGER  NOT NULL,
            scan_status TEXT     NOT NULL DEFAULT 'pending'
                CHECK (scan_status IN ('pending', 'indexed')),
            local_path  TEXT     NULL,
            created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_standards_four_elements ON standards (sha256, code, name, size)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_standards_scan_status ON standards (scan_status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_standards_code_name ON standards (code, name)")



@migration(43)
def _migrate_v43_batch_state_and_metrics(db: Any) -> None:
    """批量查询断点续传状态表 + 查询指标表。

    batch_state: 批次任务进度持久化，支持中断后断点续传。
    query_metrics: 独立指标表，与 batch_state 分离避免写锁竞争。
    """
    db.execute(
        """CREATE TABLE IF NOT EXISTS batch_state (
            batch_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','running','completed','failed','paused')),
            total_items INTEGER NOT NULL DEFAULT 0,
            completed_items INTEGER DEFAULT 0,
            failed_items INTEGER DEFAULT 0,
            overflow_pool TEXT,
            adapter_quota_snapshot TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_batch_state_status ON batch_state (status)")

    db.execute(
        """CREATE TABLE IF NOT EXISTS query_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            metric_value INTEGER NOT NULL DEFAULT 0,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batch_state(batch_id)
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_query_metrics_batch ON query_metrics (batch_id, metric_key)")


# 注意:阶段1内存缓存中的执行记录不迁移，阶段2从本次部署后开始记录

@migration(45)
def _migrate_v45_audit_logs(db: Any) -> None:
    """创建 audit_logs 表 — 无 FK 约束，user_id 允许 NULL（未认证场景）。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '{}',
            timestamp TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_logs(user_id, timestamp DESC)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")



@migration(46)
def _migrate_v46_default_user_preferences(db: Any) -> None:
    """为所有现有用户插入默认偏好（幂等，已有则跳过）。"""
    import json

    try:
        defaults = {"ui.theme": "light", "ui.lang": "zh-CN"}
        users = db.fetchall("SELECT id FROM users")
        for user in users:
            uid = user["id"]
            existing = db.fetchone(
                "SELECT COUNT(*) as cnt FROM user_preferences"
                " WHERE user_id=? AND preference_key IN ('ui.theme', 'ui.lang')",
                (uid,),
            )
            if existing and existing["cnt"] == len(defaults):
                continue
            for key, value in defaults.items():
                db.execute(
                    "INSERT OR IGNORE INTO user_preferences"
                    " (user_id, preference_key, preference_value)"
                    " VALUES (?, ?, ?)",
                    (uid, key, json.dumps(value)),
                )
    except Exception:
        pass  # 兼容旧表结构或空库场景



@migration(47)
def _migrate_v47_task_execution_history(db: Any) -> None:
    """创建 task_execution_history 表及索引（幂等）。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS task_execution_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('success', 'error')),
            error_message TEXT,
            started_at TEXT,
            finished_at TEXT NOT NULL,
            duration_ms INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_task_hist_name_time ON task_execution_history (task_name, finished_at DESC)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_hist_cleanup ON task_execution_history (task_name, finished_at)")



@migration(48)
def _migrate_v48_ensure_preference_tables(db: Any) -> None:
    """幂等补建 user_layouts 和 user_settings 表。

    生产环境修复：部分实例的 _schema_version 因未知原因跳过了 v21/v38，
    导致这两张表缺失而 /api/user/layout 和 /api/user/settings 返回 500。
    IF NOT EXISTS 确保已存在时无副作用。
    """
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_layouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            layout_key TEXT NOT NULL DEFAULT 'dashboard', layout_data TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, layout_key))
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            settings JSON NOT NULL DEFAULT '{}',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id)")



@migration(49)
def _migrate_v49_rebuild_user_preferences(db: Any) -> None:
    """重建 user_preferences 表：旧列名 key/value → user_id/preference_key/preference_value。

    迁移标记 _migration_v49_done 使用 user_id=0（系统保留 ID）。
    SQLite AUTOINCREMENT 从 1 起始，0 永远不会分配给真实用户。
    """
    db.execute("DROP TABLE IF EXISTS user_preferences")
    db.execute("""CREATE TABLE user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        preference_key TEXT NOT NULL, preference_value TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, preference_key))""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_prefs_uid_key ON user_preferences(user_id, preference_key)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_prefs_pref_key ON user_preferences(preference_key)")


# v50 兜底迁移拆分至 _migrate_v50.py，避免 G-010 单文件超限
