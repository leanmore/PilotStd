# pilotstd/core/db/migrations.py
# Schema 迁移函数（v2-v27）— 从 db.py 拆分

import logging
from typing import Any

from ._constants import migration


# === 迁移函数：按版本号递增排列，每个函数对应一个 schema 版本 ===
@migration(2)
def _migrate_v2_add_file_index(db: Any) -> None:
    """创建 file_index 表及其哈希和编码索引，用于本地文件索引。"""
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
    """创建 download_queue 和 pending_lookup 表，补全 file_index 的 status 列。"""
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
    """创建 announcement_match 表，缓存标准号与公告的匹配结果。"""
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
    """创建 rotator_state 表，记录各站点轮询器的请求计数和冷却状态。"""
    db.execute("""CREATE TABLE IF NOT EXISTS rotator_state (
        site_name TEXT PRIMARY KEY, request_count INTEGER NOT NULL DEFAULT 0,
        daily_count INTEGER NOT NULL DEFAULT 0, daily_date TEXT NOT NULL DEFAULT '',
        cooldown_until REAL NOT NULL DEFAULT 0.0, consecutive_errors INTEGER NOT NULL DEFAULT 0,
        active_url TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")


# v7-v10: 防御性表结构修改（ALTER TABLE 添加/删除列）
@migration(7)
def _migrate_v7_add_last_checked(db: Any) -> None:
    """file_index 表新增 last_checked 列及索引，用于记录上次检查时间。"""
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
    """删除 standard_info_cache 表中不再使用的 expires_at 列。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    if not cols:
        logging.getLogger("pilotstd.db").debug("v8 迁移：standard_info_cache 表不存在，跳过")
        return
    if "expires_at" in cols:
        db.execute("ALTER TABLE standard_info_cache DROP COLUMN expires_at")


@migration(9)
def _migrate_v9_add_requery_count(db: Any) -> None:
    """pending_lookup 表新增 requery_count 列，记录重查询次数。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(pending_lookup)")}
    if not cols:
        return
    if "requery_count" not in cols:
        db.execute("ALTER TABLE pending_lookup ADD COLUMN requery_count INTEGER DEFAULT 0")


@migration(10)
def _migrate_v10_add_source_and_status_history(db: Any) -> None:
    """standard_info_cache 表新增 source 和 status_history 列。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    if not cols:
        return
    if "source" not in cols:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN source TEXT NOT NULL DEFAULT 'network'")
    if "status_history" not in cols:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN status_history TEXT NOT NULL DEFAULT ''")


# v11-v12: 轮询器日限字段 + 适配器统计基础表
@migration(11)
def _migrate_v11_add_daily_limits(db: Any) -> None:
    """rotator_state 表新增每日计数和日期字段，支持日配额限制。"""
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


# v13-v14: 适配器统计扩展 + API 密钥表
@migration(13)
def _migrate_v13_adapter_stats_extend(db: Any) -> None:
    """adapter_stats 表动态补齐响应时间、冷却计数等扩展字段。"""
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
    """创建 api_keys 表，存储 API 密钥的哈希、权限范围和启用状态。"""
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
    """创建 announcement_record 表，记录公告抓取的标准号匹配明细。"""
    db.execute("""CREATE TABLE IF NOT EXISTS announcement_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_site TEXT NOT NULL,
        pid TEXT NOT NULL, announce_no TEXT, standard_number TEXT NOT NULL,
        std_name TEXT, publish_date TEXT, fetched_at TEXT NOT NULL,
        matched INTEGER DEFAULT 0, UNIQUE(source_site, pid, standard_number))""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_pid ON announcement_record(source_site, pid)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_standard ON announcement_record(standard_number)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_matched ON announcement_record(matched)")


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


# v23: 缓存系统初始化 — 数据源版本 + 缓存配置 + 多表缓存字段扩展
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


# v24: 通用任务队列 — 支持优先级、重试、超时
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


# v25-v27: 公告匹配缓存扩展 + 流水线记录 + 通知聚合
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


# v28-v29: 通知队列 + 公告记录扩展
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


# v30: 抓取失败记录 + 补抓队列 + 并发锁 + 全局应用偏好配置
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

    # 4. app_preferences — 独立全局配置表（不动 v22 创建的 user_preferences）
    db.execute(
        """CREATE TABLE IF NOT EXISTS app_preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("INSERT OR IGNORE INTO app_preferences (key, value) VALUES ('announce_since_date', '')")


# v31-v36 迁移实现拆分到独立模块（migrations.py 超过 500 行限制）
from ._migrate_v31_plus import (  # noqa: E402
    _migrate_v31_monitor_stats,
    _migrate_v32_cleanup_dead_tables,
    _migrate_v33_adapter_state,
    _migrate_v34_drop_old_adapter_tables,
    _migrate_v35_notification_policy,
    _migrate_v36_announcement_structure,
    _migrate_v37_user_notification_config,
    _migrate_v39_announcement_source_type,
)

migration(31)(_migrate_v31_monitor_stats)
migration(32)(_migrate_v32_cleanup_dead_tables)
migration(33)(_migrate_v33_adapter_state)
migration(34)(_migrate_v34_drop_old_adapter_tables)
migration(35)(_migrate_v35_notification_policy)
migration(36)(_migrate_v36_announcement_structure)
migration(37)(_migrate_v37_user_notification_config)
migration(39)(_migrate_v39_announcement_source_type)


# v38: 用户偏好聚合存储表（JSON 格式，与现有 user_preferences KV 表并存）
@migration(38)
def _migrate_v38_user_settings(db) -> None:
    """新增 user_settings 表（JSON 聚合存储），与现有 user_preferences（KV 存储）并存。"""
    logger = logging.getLogger(__name__)

    # 防御性检查：查询 sqlite_master 确认表是否已存在
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
