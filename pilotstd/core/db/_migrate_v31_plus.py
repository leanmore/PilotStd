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


# v33: 三表合一 — rotator_state + adapter_stats + adapter_health → adapter_state
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
    """将合并后被取代的三张旧表重命名为备份表，确认稳定后可手动删除。"""
    for table in ("rotator_state", "adapter_stats", "adapter_health"):
        try:
            db.execute(f"ALTER TABLE {table} RENAME TO {table}_backup_v34")
        except Exception:
            pass  # 表不存在则跳过


# v35: 通知策略配置 — 渠道事件订阅统一管理
def _migrate_v35_notification_policy(db: Any) -> None:
    """新建 notification_policy 表，统一存储渠道事件订阅配置。"""
    import json

    db.execute(
        "CREATE TABLE IF NOT EXISTS notification_policy ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,"
        "channel TEXT NOT NULL, enabled INTEGER DEFAULT 1,"
        "events TEXT NOT NULL DEFAULT '[]',"
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "UNIQUE(user_id, channel))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_policy_user ON notification_policy(user_id)")

    # 数据迁移：从 config.json 的 notification.rules 读取现有规则，
    # 反转为 (channel → events) 映射写入 notification_policy
    try:
        from pilotstd.core.config import ConfigManager as _CM

        cfg = _CM()
        channel_events: dict[str, list[str]] = {}
        for key, value in cfg._data.items():
            if key.startswith("notification.rules.") and isinstance(value, list) and value:
                event_type = key[len("notification.rules.") :]
                for ch_name in value:
                    if ch_name not in channel_events:
                        channel_events[ch_name] = []
                    channel_events[ch_name].append(event_type)

        for ch_name, events in channel_events.items():
            db.execute(
                "INSERT OR REPLACE INTO notification_policy (user_id, channel, enabled, events) VALUES (NULL, ?, 1, ?)",
                (ch_name, json.dumps(events, ensure_ascii=False)),
            )
    except Exception:
        pass  # 配置文件不可用时跳过数据迁移


def _v36_new_tables(db: Any) -> None:
    """创建 announcements / user_favorites / date_reminder_log 三张新表。"""
    db.execute(
        "CREATE TABLE IF NOT EXISTS announcements ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "source_site TEXT NOT NULL,"
        "pid TEXT NOT NULL,"
        "announce_no TEXT NOT NULL,"
        "title TEXT NOT NULL,"
        "publish_date TEXT,"
        "source_url TEXT,"
        "attachment_url TEXT,"
        "raw_data TEXT,"
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "UNIQUE(source_site, pid))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_announcements_source_site_pid ON announcements(source_site, pid)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_announcements_announce_no ON announcements(announce_no)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_announcements_publish_date ON announcements(publish_date)")

    db.execute(
        "CREATE TABLE IF NOT EXISTS user_favorites ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "user_id INTEGER NOT NULL,"
        "record_id INTEGER NOT NULL,"
        "status TEXT DEFAULT 'pending',"
        "local_path TEXT,"
        "error_message TEXT,"
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "FOREIGN KEY (user_id) REFERENCES users(id),"
        "FOREIGN KEY (record_id) REFERENCES announcement_record(id),"
        "UNIQUE(user_id, record_id))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_favorites_user_id ON user_favorites(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_favorites_status ON user_favorites(status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_favorites_record_id ON user_favorites(record_id)")

    db.execute(
        "CREATE TABLE IF NOT EXISTS date_reminder_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "user_id INTEGER NOT NULL,"
        "record_id INTEGER NOT NULL,"
        "remind_type TEXT NOT NULL,"
        "days_before INTEGER NOT NULL,"
        "sent_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "FOREIGN KEY (user_id) REFERENCES users(id),"
        "FOREIGN KEY (record_id) REFERENCES announcement_record(id),"
        "UNIQUE(user_id, record_id, remind_type, days_before))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_date_reminder_log_user_id ON date_reminder_log(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_date_reminder_log_record_id ON date_reminder_log(record_id)")


def _v36_extend_record(db: Any) -> None:
    """扩展 announcement_record：新增字段 + 索引（announce_no 已存在，跳过）。"""
    _cols = [
        ("announcement_id", "INTEGER"),
        ("row_index", "INTEGER"),
        ("implement_date", "TEXT"),
        ("expiry_date", "TEXT"),
        ("superseded_by", "TEXT"),
        ("status", "TEXT DEFAULT 'draft'"),
        ("confidence", "REAL DEFAULT 0.0"),
        ("raw_text", "TEXT"),
        ("parser_engine", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "TEXT"),
        ("updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
    ]
    for col_name, col_def in _cols:
        try:
            db.execute(f"ALTER TABLE announcement_record ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass

    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_announcement_record_announcement_id ON announcement_record(announcement_id)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_announcement_record_status ON announcement_record(status)")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_announcement_record_standard_number ON announcement_record(standard_number)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_announcement_record_implement_date ON announcement_record(implement_date)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_announcement_record_expiry_date ON announcement_record(expiry_date)")


def _v36_migrate_data(db: Any) -> None:
    """存量数据迁移：按 (source_site, pid) 提取公告头 → announcements，回填 announcement_id。"""
    rows = db.fetchall(
        "SELECT source_site, pid,"
        " MAX(announce_no) AS announce_no,"
        " COALESCE(MAX(announcement_title), '公告 ' || MAX(announce_no)) AS title,"
        " MAX(publish_date) AS publish_date"
        " FROM announcement_record"
        " WHERE pid IS NOT NULL"
        " GROUP BY source_site, pid"
    )
    for source_site, pid, announce_no, title, publish_date in rows:
        db.execute(
            "INSERT OR IGNORE INTO announcements"
            " (source_site, pid, announce_no, title, publish_date, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (source_site, pid, announce_no, title, publish_date),
        )

    db.execute(
        "UPDATE announcement_record"
        " SET announcement_id = ("
        "  SELECT a.id FROM announcements a"
        "  WHERE a.source_site = announcement_record.source_site"
        "    AND a.pid = announcement_record.pid"
        " )"
        " WHERE pid IS NOT NULL"
    )
    db.execute("UPDATE announcement_record SET status = 'draft' WHERE status IS NULL")


def _migrate_v36_announcement_structure(db: Any) -> None:
    """v36: 公告数据结构重构 — 拆分 announcements + 扩展 announcement_record + 新建收藏/提醒表。"""
    # v36 分三步执行：建新表 → 扩展旧表字段 → 存量数据迁移
    _v36_new_tables(db)
    _v36_extend_record(db)
    _v36_migrate_data(db)


def _migrate_v37_user_notification_config(db: Any) -> None:
    """v37: 通知渠道配置按用户隔离。

    1. 防御性加列（notification_policy.user_id，v35 已建但兜底）
    2. 新建 user_credentials 表
    3. 从 config.json 迁移渠道凭证到 user_credentials (user_id=1)
    4. notification_policy 现有记录分配 user_id=1
    5. 标记 config.json 已迁移
    """
    import json as _json
    import os as _os

    # 1. 防御性加列
    try:
        db.execute("ALTER TABLE notification_policy ADD COLUMN user_id INTEGER")
    except Exception:
        pass

    # 2. 建表
    db.execute(
        'CREATE TABLE IF NOT EXISTS "user_credentials" ('
        '"id" INTEGER PRIMARY KEY AUTOINCREMENT,'
        '"user_id" INTEGER NOT NULL,'
        '"channel" TEXT NOT NULL,'
        '"credentials" TEXT NOT NULL,'
        '"created_at" TEXT DEFAULT CURRENT_TIMESTAMP,'
        '"updated_at" TEXT DEFAULT CURRENT_TIMESTAMP,'
        'UNIQUE("user_id", "channel"))'
    )
    db.execute('CREATE INDEX IF NOT EXISTS "idx_user_creds_user" ON "user_credentials"("user_id")')

    # 3. 从 config.json 迁移渠道凭证
    try:
        from pilotstd.core.config import ConfigManager as _CM
        from pilotstd.core.config.crypto import _get_fernet

        cfg = _CM()
        channels = (cfg._data.get("notification") or {}).get("channels") or {}
        if channels:
            config_dir = _os.path.dirname(cfg._filepath)
            fernet = _get_fernet(config_dir)
            for ch_name, ch_cfg in channels.items():
                if isinstance(ch_cfg, dict) and ch_cfg:
                    plain = _json.dumps(ch_cfg, ensure_ascii=False)
                    encrypted = fernet.encrypt(plain.encode()).decode()
                    db.execute(
                        'INSERT OR REPLACE INTO "user_credentials"'
                        ' ("user_id", "channel", "credentials") VALUES (1, ?, ?)',
                        (ch_name, encrypted),
                    )
    except Exception:
        pass

    # 4. 更新策略表
    db.execute('UPDATE "notification_policy" SET "user_id" = 1 WHERE "user_id" IS NULL')

    # 5. 标记已迁移
    try:
        from pilotstd.core.config import ConfigManager as _CM

        cfg = _CM()
        cfg.set("notification._migrated_to_db", True)
        cfg.save()
    except Exception:
        pass
