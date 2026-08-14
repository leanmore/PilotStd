# 模块：项目//_脚本
# 阶段4:日期提醒—扫描实施/作废/代替标准的到期日期，通过通知管道推送

import logging
from datetime import date, timedelta
from typing import Any, Optional

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database

logger = logging.getLogger(__name__)

_REMIND_DAYS = [30, 15, 7, 0]


def _target_dates() -> dict[int, str]:
    """计算未来需要提醒的日期（30/15/7/0 天后）。键=天数，值=ISO 日期字符串。"""
    today = date.today()
    return {d: (today + timedelta(days=d)).isoformat() for d in _REMIND_DAYS}


# _抓取__—从公告数据库中查找即将到期的记录（实施/作废/代替三种类型）
def _fetch_due_records(db: Database) -> list[dict[str, Any]]:
    """从公告数据库中查找即将到期的记录。查询实施/作废/代替三种到期类型。"""
    target_dates = list(_target_dates().values())
    ph = ",".join("?" for _ in target_dates)

    sql = f"""
        SELECT id, standard_number, std_name, implement_date, expiry_date,
               superseded_by,
               CASE
                   WHEN implement_date IS NOT NULL AND implement_date != ''
                        AND implement_date IN ({ph}) THEN 'implement'
                   WHEN expiry_date IS NOT NULL AND expiry_date != ''
                        AND expiry_date IN ({ph}) THEN 'expiry'
                   WHEN superseded_by IS NOT NULL AND superseded_by != ''
                        AND EXISTS (
                            SELECT 1 FROM announcement_record AS r2
                            WHERE r2.standard_number = announcement_record.superseded_by
                              AND r2.status = 'approved'
                              AND r2.implement_date IN ({ph})
                        ) THEN 'expiry_implied'
               END AS remind_type,
               (SELECT implement_date FROM announcement_record AS r2
                WHERE r2.standard_number = announcement_record.superseded_by
                  AND r2.status = 'approved'
                  AND r2.implement_date IN ({ph})
                LIMIT 1) AS implied_date
        FROM announcement_record
        WHERE status = 'approved'
          AND (
              (implement_date IS NOT NULL AND implement_date != '' AND implement_date IN ({ph}))
              OR (expiry_date IS NOT NULL AND expiry_date != '' AND expiry_date IN ({ph}))
              OR (superseded_by IS NOT NULL AND superseded_by != ''
                  AND EXISTS (
                      SELECT 1 FROM announcement_record AS r2
                      WHERE r2.standard_number = announcement_record.superseded_by
                        AND r2.status = 'approved'
                        AND r2.implement_date IN ({ph})
                  ))
          )
    """
    # 7处占位符，每处都需要相同的日期参数列表
    cursor = db.execute(sql, target_dates * 7)
    return cursor.fetchall()


def _process_record(rec: dict, today: date, db: Database, notification_mgr: Any, stats: dict) -> None:
    """处理单条到期记录：去重检查 → 查找关注用户 → 发送通知 → 记录日志。"""
    remind_type = rec["remind_type"]
    if not remind_type:
        return

    if remind_type == "implement":
        target_str = rec["implement_date"]
    elif remind_type == "expiry":
        target_str = rec["expiry_date"]
    else:
        target_str = rec.get("implied_date") or rec["implement_date"]
    if not target_str:
        return

    days_before = (date.fromisoformat(target_str) - today).days
    if days_before not in _REMIND_DAYS:
        return

    record_id = rec["id"]
    # ✅任务2-：_下载无_，连接获取；
    # =''现在在_下载表中
    cursor = db.execute(
        "SELECT DISTINCT uf.user_id FROM favorite_downloads fd"
        " JOIN user_favorites uf ON fd.favorite_id = uf.id"
        " WHERE fd.record_id=? AND fd.status='done'",
        (record_id,),
    )
    user_ids = [r["user_id"] for r in cursor.fetchall()]
    if not user_ids:
        return

    for uid in user_ids:
        cursor = db.execute(
            "SELECT 1 FROM date_reminder_log"
            " WHERE user_id=? AND record_id=? AND remind_type=? AND days_before=? LIMIT 1",
            (uid, record_id, remind_type, days_before),
        )
        if cursor.fetchone():
            stats["skipped"] += 1
            continue

        try:
            notification_mgr.send_event(
                "date_reminder",
                {
                    "user_id": uid,
                    "record_id": record_id,
                    "standard_number": rec["standard_number"],
                    "std_name": rec["std_name"] or "",
                    "days_before": days_before,
                    "remind_type": remind_type,
                },
            )
            stats["sent"] += 1
        except Exception:
            logger.exception("通知发送失败: uid=%s rec=%s", uid, record_id)
            continue

        db.execute(
            "INSERT INTO date_reminder_log"
            " (user_id, record_id, remind_type, days_before, sent_at)"
            " VALUES (?, ?, ?, ?, datetime('now'))",
            (uid, record_id, remind_type, days_before),
        )


# __—日期提醒主任务，由调度器定时调用，扫描到期标准并推送通知
def run_date_reminder(notification_mgr: Any = None) -> dict[str, Any]:
    """日期提醒主任务。由 scheduler 定时调用，notification_mgr 由包装器注入。"""
    if notification_mgr is None:
        from pilotstd.manager.facade import StandardManager  # noqa: E402

        notification_mgr = StandardManager().notification_mgr

    db: Optional[Database] = None
    stats: dict[str, Any] = {"scanned": 0, "sent": 0, "skipped": 0}
    try:
        db = Database(get_db_path())
        records = _fetch_due_records(db)
        stats["scanned"] = len(records)
        if not records:
            return stats

        today = date.today()
        for rec in records:
            _process_record(rec, today, db, notification_mgr, stats)

        logger.info(
            "日期提醒完成: scanned=%d sent=%d skipped=%d",
            stats["scanned"],
            stats["sent"],
            stats["skipped"],
        )
    except Exception:
        logger.exception("日期提醒失败")
        raise
    finally:
        if db:
            db.close()
    return stats
