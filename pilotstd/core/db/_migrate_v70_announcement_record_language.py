# 模块：v70 公告记录语种/外文名
"""为 announcement_record 增加 language / foreign_name，并把唯一键扩展为含语种。

背景：GB 2026 年第29/39号同一标准号有英文版、德文版等多行；旧唯一键
(source_site,pid,standard_number) 会把不同语种合并，导致计数少 1~2 条。
迁移不可变：不修改 v15，新增 v70 重建表。
"""

from __future__ import annotations

from typing import Any

from ._constants import migration

_TABLE_SQL = (  # i18n-allow: 历史默认值原样保留
    """
CREATE TABLE announcement_record_v70 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_site TEXT NOT NULL,
    pid TEXT NOT NULL,
    announce_no TEXT,
    standard_number TEXT NOT NULL,
    std_name TEXT,
    publish_date TEXT,
    fetched_at TEXT NOT NULL,
    matched INTEGER DEFAULT 0,
    source_version TEXT DEFAULT 'initial',
    data_state TEXT DEFAULT 'fresh',
    last_accessed_at TEXT,
    announcement_title TEXT,
    standard_count INTEGER,
    announcement_id INTEGER,
    row_index INTEGER,
    implement_date TEXT,
    expiry_date TEXT,
    superseded_by TEXT,
    status TEXT DEFAULT 'draft',
    confidence REAL DEFAULT 0.0,
    raw_text TEXT,
    parser_engine TEXT,
    approved_by INTEGER,
    approved_at TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    source_type TEXT DEFAULT '网页解析',  -- i18n-allow: 历史默认值原样保留
    standard_type TEXT NOT NULL DEFAULT 'Unknown',
    final_name TEXT,
    language TEXT DEFAULT '',
    foreign_name TEXT DEFAULT '',
    UNIQUE(source_site, pid, standard_number, language)
)
"""

)

_INSERT_SQL = """
INSERT OR IGNORE INTO announcement_record_v70 (
    id, source_site, pid, announce_no, standard_number, std_name, publish_date, fetched_at,
    matched, source_version, data_state, last_accessed_at, announcement_title, standard_count,
    announcement_id, row_index, implement_date, expiry_date, superseded_by, status,
    confidence, raw_text, parser_engine, approved_by, approved_at, updated_at,
    source_type, standard_type, final_name, language, foreign_name
)
SELECT
    id, source_site, pid, announce_no, standard_number, std_name, publish_date, fetched_at,
    matched, source_version, data_state, last_accessed_at, announcement_title, standard_count,
    announcement_id, row_index, implement_date, expiry_date, superseded_by, status,
    confidence, raw_text, parser_engine, approved_by, approved_at, updated_at,
    source_type, standard_type, final_name, COALESCE(language, ''), COALESCE(foreign_name, '')
FROM announcement_record
"""


@migration(70)
def _migrate_v70_announcement_record_language(db: Any) -> None:
    """重建 announcement_record，加入语种/外文名并扩展唯一键。"""
    cols = {row["name"] for row in db.fetchall("PRAGMA table_info(announcement_record)")}
    if not cols:
        return
    # 上次失败可能留下半成品表；先清理，保证可重入
    db.execute("DROP TABLE IF EXISTS announcement_record_v70")

    if "language" not in cols:
        db.execute("ALTER TABLE announcement_record ADD COLUMN language TEXT DEFAULT ''")
    if "foreign_name" not in cols:
        db.execute("ALTER TABLE announcement_record ADD COLUMN foreign_name TEXT DEFAULT ''")

    indexes = [
        row["sql"]
        for row in db.fetchall(
            "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='announcement_record' AND sql IS NOT NULL"
        )
    ]
    fk_on = db.fetchone("PRAGMA foreign_keys")
    fk_enabled = bool(fk_on and list(fk_on.values())[0])
    if fk_enabled:
        db.execute("PRAGMA foreign_keys=OFF")
    try:
        db.execute(_TABLE_SQL)
        db.execute(_INSERT_SQL)
        db.execute("DROP TABLE announcement_record")
        db.execute("ALTER TABLE announcement_record_v70 RENAME TO announcement_record")
        for sql in indexes:
            db.execute(sql)
    finally:
        if fk_enabled:
            db.execute("PRAGMA foreign_keys=ON")
