# pilotstd/tasks/date_reminder.py
# Phase 4b: 日期提醒 — 扫描实施日期到期的标准，通过通知管道推送

import logging
from datetime import date, timedelta
from typing import Any, Optional

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database

logger = logging.getLogger(__name__)

_REMIND_DAYS = [30, 15, 7, 0]


def _notify_record(rec: dict, today: date, db: Database, notification_mgr: Any, stats: dict) -> None:
    """处理单条记录：查收藏用户 → 去重 → send_event → 写日志。"""
    record_id = rec["id"]
    impl_date = rec["implement_date"]
    days_before = (date.fromisoformat(impl_date) - today).days
    if days_before not in _REMIND_DAYS:
        return

    cursor = db.execute(
        "SELECT DISTINCT user_id FROM user_favorites WHERE record_id=? AND status='done'",
        (record_id,),
    )
    user_ids = [r["user_id"] for r in cursor.fetchall()]
    if not user_ids:
        return

    for user_id in user_ids:
        cursor = db.execute(
            "SELECT 1 FROM date_reminder_log"
            " WHERE user_id=? AND record_id=? AND remind_type=? AND days_before=? LIMIT 1",
            (user_id, record_id, "implement", days_before),
        )
        if cursor.fetchone():
            stats["skipped"] += 1
            continue

        notification_mgr.send_event(
            "date_reminder",
            {
                "user_id": user_id,
                "standard_number": rec["standard_number"],
                "std_name": rec["std_name"] or "",
                "implement_date": impl_date,
                "days_before": days_before,
            },
        )
        db.execute(
            "INSERT INTO date_reminder_log"
            " (user_id, record_id, remind_type, days_before, sent_at)"
            " VALUES (?, ?, 'implement', ?, datetime('now'))",
            (user_id, record_id, days_before),
        )
        stats["notified"] += 1


def run_date_reminder(notification_mgr: Any = None) -> dict[str, Any]:
    """日期提醒主任务。"""
    if notification_mgr is None:
        from pilotstd.manager.facade import StandardManager  # noqa: E402

        notification_mgr = StandardManager().notification_mgr

    db: Optional[Database] = None
    stats: dict[str, Any] = {"scanned": 0, "notified": 0, "skipped": 0}
    try:
        db = Database(get_db_path())
        today = date.today()
        target_dates = [(today + timedelta(days=d)).isoformat() for d in _REMIND_DAYS]
        placeholders = ",".join("?" for _ in target_dates)

        cursor = db.execute(
            f"SELECT id, standard_number, std_name, implement_date"
            f" FROM announcement_record"
            f" WHERE status='approved' AND implement_date IS NOT NULL AND implement_date!=''"
            f" AND implement_date IN ({placeholders})"
            f" ORDER BY implement_date",
            target_dates,
        )
        records = cursor.fetchall()
        stats["scanned"] = len(records)
        if not records:
            return stats

        for rec in records:
            _notify_record(rec, today, db, notification_mgr, stats)

        logger.info(
            "日期提醒完成: scanned=%d notified=%d skipped=%d",
            stats["scanned"],
            stats["notified"],
            stats["skipped"],
        )
    except Exception as e:
        logger.error("日期提醒失败: %s", e, exc_info=True)
    finally:
        if db:
            db.close()
    return stats
