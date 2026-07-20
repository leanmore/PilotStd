# pilotstd/core/db/_migrate_v37_plus.py
# v37-v40 迁移 — 从 _migrate_v31_plus.py 拆分

from typing import Any


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


def _migrate_v39_announcement_source_type(db: Any) -> None:
    """v39: 公告记录新增 source_type + announcements 新增 parse_status。"""
    for col_name, col_def in [
        ("source_type", "TEXT DEFAULT '网页解析'"),
    ]:
        try:
            db.execute(f"ALTER TABLE announcement_record ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass

    for col_name, col_def in [
        ("parse_status", "TEXT DEFAULT 'pending'"),
    ]:
        try:
            db.execute(f"ALTER TABLE announcements ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass


def _migrate_v40_ensure_columns(db: Any) -> None:
    """v40: 逐列检查 announcement_record 和 announcements 表，补遗漏的列。"""
    import logging as _logging

    _log = _logging.getLogger("migrate.v40")

    _record_cols: list[tuple[str, str]] = [
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
        ("source_type", "TEXT DEFAULT '网页解析'"),
    ]

    existing = {r[1] for r in db.execute("PRAGMA table_info(announcement_record)")}
    for col_name, col_def in _record_cols:
        if col_name not in existing:
            db.execute(f"ALTER TABLE announcement_record ADD COLUMN {col_name} {col_def}")
            _log.info("补列 announcement_record.%s %s", col_name, col_def)

    _ann_cols = [("parse_status", "TEXT DEFAULT 'pending'")]
    existing_ann = {r[1] for r in db.execute("PRAGMA table_info(announcements)")}
    for col_name, col_def in _ann_cols:
        if col_name not in existing_ann:
            db.execute(f"ALTER TABLE announcements ADD COLUMN {col_name} {col_def}")
            _log.info("补列 announcements.%s %s", col_name, col_def)
