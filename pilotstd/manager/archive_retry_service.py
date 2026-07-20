# pilotstd/manager/archive_retry_service.py
"""收藏归档重试服务 — 冷却期 + 重试上限 + 公平调度 + 失败通知。

由 APScheduler 定时任务（每天凌晨4点）调用 retry_pending()。

环境变量：
  ARCHIVE_COOLDOWN_DAYS  冷却期天数（默认 28）
  ARCHIVE_MAX_RETRIES    最大重试次数（默认 7）
"""

import logging
import os
from datetime import date, timedelta
from typing import Any

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database
from pilotstd.tasks.favorite_download import download_to_inbox

logger = logging.getLogger(__name__)

_COOLDOWN_DAYS = int(os.environ.get("ARCHIVE_COOLDOWN_DAYS", "28"))
_MAX_RETRIES = int(os.environ.get("ARCHIVE_MAX_RETRIES", "7"))
_BATCH_LIMIT = 20


class ArchiveRetryService:
    """定时扫描 pending/failed 收藏，在冷却期满后重试下载归档。"""

    def __init__(self, mgr: Any):
        self._mgr = mgr

    def retry_pending(self) -> dict:
        """扫描待重试的收藏记录并逐条执行下载任务。

        筛选条件：
        - status IN ('pending', 'failed')
        - archive_retry_count < 7（未达上限）
        - publish_date 为 NULL 或已过 28 天冷却期

        公平调度：ORDER BY last_archive_attempt ASC NULLS FIRST, updated_at ASC
        每批最多处理 20 条。
        """
        db = Database(get_db_path())
        today = date.today().isoformat()
        cooldown_cutoff = (date.today() - timedelta(days=_COOLDOWN_DAYS)).isoformat()
        try:
            # 公平调度：按上次重试时间升序，保证等最久的先处理
            rows = db.fetchall(
                "SELECT id, user_id, record_id, publish_date, archive_retry_count, error_message"
                " FROM user_favorites"
                " WHERE status IN ('pending','failed')"
                " AND (archive_retry_count IS NULL OR archive_retry_count < ?)"
                " AND (publish_date IS NULL OR publish_date <= ?)"
                " ORDER BY last_archive_attempt ASC NULLS FIRST, updated_at ASC"
                " LIMIT ?",
                (_MAX_RETRIES, cooldown_cutoff, _BATCH_LIMIT),
            )
            if not rows:
                return {"ok": True, "total": 0, "success": 0}

            success = 0
            for row in rows:
                try:
                    download_to_inbox(row["id"], row["user_id"], row["record_id"])
                    # 成功后重置重试计数
                    db.execute(
                        "UPDATE user_favorites SET archive_retry_count = 0,"
                        " last_archive_attempt = ?, updated_at = datetime('now')"
                        " WHERE id = ?",
                        (today, row["id"]),
                    )
                    success += 1
                except Exception as e:
                    new_count = (row["archive_retry_count"] or 0) + 1
                    error_msg = str(e)[:500]
                    if new_count >= _MAX_RETRIES:
                        # 超上限：标记 abandoned 并通知用户，不再重试
                        db.execute(
                            "UPDATE user_favorites SET status = 'abandoned',"
                            " archive_retry_count = ?, error_message = ?,"
                            " last_archive_attempt = ?, updated_at = datetime('now')"
                            " WHERE id = ?",
                            (new_count, error_msg, today, row["id"]),
                        )
                        self._notify_abandoned(row["user_id"], row["record_id"], error_msg)
                    else:
                        db.execute(
                            "UPDATE user_favorites SET archive_retry_count = ?,"
                            " error_message = ?, last_archive_attempt = ?,"
                            " updated_at = datetime('now') WHERE id = ?",
                            (new_count, error_msg, today, row["id"]),
                        )
                    logger.warning(
                        "归档重试失败 favorite_id=%s (第%d次): %s",
                        row["id"],
                        new_count,
                        e,
                    )
            logger.info("归档重试完成: %d/%d 成功", success, len(rows))
            return {"ok": True, "total": len(rows), "success": success}
        finally:
            db.close()

    def _notify_abandoned(self, user_id: int, record_id: int, error_msg: str) -> None:
        """通知用户归档已放弃（重试7次均失败）。"""
        try:
            db = Database(get_db_path())
            row = db.fetchone(
                "SELECT standard_number, std_name FROM announcement_record WHERE id = ?",
                (record_id,),
            )
            std_info = f"{row['standard_number']} {row['std_name']}" if row else f"record#{record_id}"
            db.close()

            notification_mgr = getattr(self._mgr, "notification_mgr", None)
            if notification_mgr:
                notification_mgr.send_event(
                    "archive_abandoned",
                    {
                        "user_id": user_id,
                        "record_id": record_id,
                        "standard_info": std_info,
                        "error": error_msg,
                    },
                )
        except Exception:
            logger.warning("发送归档放弃通知失败", exc_info=True)
