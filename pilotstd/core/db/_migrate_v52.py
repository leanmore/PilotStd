# 模块：项目/核心/数据库/迁移_v52脚本
# v52 兜底迁移 — user_favorites 补 publish_date 列，修复收藏接口 500
# 根因：部分生产库在 v36 的 ALTER 列补全逻辑（publish_date/last_archive_attempt/
#       archive_retry_count）落地前就已记录 v36 迁移，导致 publish_date 列从未
#       创建；docker/api/favorites.py 收藏时 INSERT 报
#       "table user_favorites has no column named publish_date" → /api/favorites 500。

from typing import Any

# user_favorites 目标列结构：与 v36 最终形态一致（v50 同款"兜底补建"范式，
# IF NOT EXISTS 保证表已存在时零副作用）
_USER_FAVORITES_DDL = """CREATE TABLE IF NOT EXISTS user_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    record_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    local_path TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    publish_date TEXT,
    last_archive_attempt TEXT,
    archive_retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (record_id) REFERENCES announcement_record(id),
    UNIQUE(user_id, record_id))"""


def _migrate_v52_ensure_user_favorites_publish_date(db: Any) -> None:
    """兜底补全 user_favorites.publish_date 列（幂等，可重复执行）。

    业务语义：publish_date 是标准的发布日期（收藏时从 announcement_record 复制），
    允许为 NULL——未知发布日期表示无冷却期限制（archive_retry_service.py 显式
    处理 NULL）。因此不加 DEFAULT datetime('now')，避免把收藏时间误当作发布日期、
    污染冷却期计算语义。
    """
    db.execute(_USER_FAVORITES_DDL)
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")}
    if "publish_date" not in cols:
        db.execute("ALTER TABLE user_favorites ADD COLUMN publish_date TEXT")
