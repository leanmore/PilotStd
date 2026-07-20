# pilotstd/core/db/_migrate_v2_v15.py
# v2-v15 迁移 — 从 migrations.py 拆分

# pilotstd/core/db/_migrate_v2_v15.py
# v2-v15 迁移 — 从 migrations.py 拆分

# pilotstd/core/db/_migrate_v2_v15.py
# v2-v15 迁移 — 从 migrations.py 拆分

import logging
from typing import Any


# === 迁移函数：按版本号递增排列，每个函数对应一个 schema 版本 ===
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


def _migrate_v4_add_fetch_checkpoint(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS fetch_checkpoint (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_site TEXT NOT NULL UNIQUE,
        last_fetched_at TEXT NOT NULL DEFAULT '', last_notice_date TEXT NOT NULL DEFAULT '')""")


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


def _migrate_v6_add_rotator_state(db: Any) -> None:
    """创建 rotator_state 表，记录各站点轮询器的请求计数和冷却状态。"""
    db.execute("""CREATE TABLE IF NOT EXISTS rotator_state (
        site_name TEXT PRIMARY KEY, request_count INTEGER NOT NULL DEFAULT 0,
        daily_count INTEGER NOT NULL DEFAULT 0, daily_date TEXT NOT NULL DEFAULT '',
        cooldown_until REAL NOT NULL DEFAULT 0.0, consecutive_errors INTEGER NOT NULL DEFAULT 0,
        active_url TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")


# v7-v10: 防御性表结构修改（ALTER TABLE 添加/删除列）
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


def _migrate_v8_drop_expires_at(db: Any) -> None:
    """删除 standard_info_cache 表中不再使用的 expires_at 列。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    if not cols:
        logging.getLogger("pilotstd.db").debug("v8 迁移：standard_info_cache 表不存在，跳过")
        return
    if "expires_at" in cols:
        db.execute("ALTER TABLE standard_info_cache DROP COLUMN expires_at")


def _migrate_v9_add_requery_count(db: Any) -> None:
    """pending_lookup 表新增 requery_count 列，记录重查询次数。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(pending_lookup)")}
    if not cols:
        return
    if "requery_count" not in cols:
        db.execute("ALTER TABLE pending_lookup ADD COLUMN requery_count INTEGER DEFAULT 0")


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
def _migrate_v11_add_daily_limits(db: Any) -> None:
    """rotator_state 表新增每日计数和日期字段，支持日配额限制。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(rotator_state)")}
    if not cols:
        return
    if "daily_count" not in cols:
        db.execute("ALTER TABLE rotator_state ADD COLUMN daily_count INTEGER NOT NULL DEFAULT 0")
    if "daily_date" not in cols:
        db.execute("ALTER TABLE rotator_state ADD COLUMN daily_date TEXT NOT NULL DEFAULT ''")


def _migrate_v12_adapter_stats(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS adapter_stats (
        adapter_name TEXT PRIMARY KEY, total_queries INTEGER DEFAULT 0,
        successful_queries INTEGER DEFAULT 0,
        last_updated TEXT DEFAULT (datetime('now', 'localtime')))""")


# v13-v14: 适配器统计扩展 + API 密钥表
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


