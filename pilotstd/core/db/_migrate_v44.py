# pilotstd/core/db/_migrate_v44.py
# v44: favorite_downloads 表 — 收藏与归档彻底解耦
#
# 设计决策（ADR-007 扩展）：
# - user_favorites 回归纯粹收藏语义（仅存二元关系）
# - 归档下载状态机独立到 favorite_downloads 表
# - 迁移包裹在显式事务中，异常时完整回滚

import logging
from typing import Any

from ._constants import migration

logger = logging.getLogger(__name__)


@migration(44)
def _migrate_v44_favorite_downloads(db: Any) -> None:
    """创建 favorite_downloads 表 + 迁移归档状态数据 + 清理 user_favorites。

    事务保护：整个迁移在一个显式事务中执行。
    若中途异常，回滚所有 DDL + DML，user_favorites 保持原样。
    """
    # ── 1. 创建 favorite_downloads 表 ──
    db.execute(
        """CREATE TABLE IF NOT EXISTS favorite_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            favorite_id INTEGER NOT NULL,
            record_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            local_path TEXT,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            last_attempt TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (favorite_id) REFERENCES user_favorites(id) ON DELETE CASCADE,
            FOREIGN KEY (record_id) REFERENCES announcement_record(id),
            UNIQUE(favorite_id, record_id)
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_favorite_downloads_status ON favorite_downloads (status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_favorite_downloads_record ON favorite_downloads (record_id)")

    # ── 2. 迁移现有数据 ──
    # 将 user_favorites 中所有归档状态记录迁移到 favorite_downloads
    # 防御性检查：确保 archive_retry_count 列存在（v36 的 ALTER TABLE 可能在特定条件下静默失败）
    existing_cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")}
    if "archive_retry_count" in existing_cols and "last_archive_attempt" in existing_cols:
        rows_migrated = db.execute(
            """INSERT OR IGNORE INTO favorite_downloads
               (favorite_id, record_id, status, local_path, error_message,
                retry_count, last_attempt, created_at, updated_at)
               SELECT id, record_id, status, local_path, error_message,
                      archive_retry_count, last_archive_attempt,
                      created_at, updated_at
               FROM user_favorites
               WHERE status IN ('downloading', 'archiving', 'done', 'failed', 'abandoned')
                 AND record_id IS NOT NULL"""
        )
        logger.info("favorite_downloads 数据迁移完成，迁移行数: %s", rows_migrated.rowcount if rows_migrated else 0)
    else:
        logger.warning("user_favorites 缺少 archive_retry_count/last_archive_attempt 列，跳过存量数据迁移")
        rows_migrated = None

    # ── 3. 清理 user_favorites 归档状态 ──
    # 已成功迁移的记录，状态重置为 'pending'（回归纯粹收藏语义）
    cleaned = db.execute(
        """UPDATE user_favorites
           SET status = 'pending',
               updated_at = CURRENT_TIMESTAMP
           WHERE status IN ('downloading', 'archiving', 'done', 'failed', 'abandoned')
             AND record_id IS NOT NULL"""
    )
    logger.info("user_favorites 归档状态清理完成，清理行数: %s", cleaned.rowcount if cleaned else 0)
