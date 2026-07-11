# pilotstd/tasks/date_reminder.py
# Phase 4b: 日期提醒 — 扫描实施日期到期的标准，通过 Webhook 推送提醒
#
# 不依赖 NotificationManager 管道，直接从 ConfigManager 读 Webhook URL 发送。
# 支持企业微信/飞书/钉钉三种 Webhook 渠道。

import logging
from datetime import date, timedelta
from typing import Any, Optional

import requests

from pilotstd.core.config import ConfigManager, get_db_path
from pilotstd.core.db.database import Database

logger = logging.getLogger(__name__)

_REMIND_DAYS = [30, 15, 7, 0]

_CHANNEL_CONFIGS = [
    ("wechat", "notification.channels.wechat.webhook_url"),
    ("feishu", "notification.channels.feishu.webhook_url"),
    ("dingtalk", "notification.channels.dingtalk.webhook_url"),
]


def _get_webhook_urls(cfg: ConfigManager) -> list[tuple[str, str]]:
    """读取已配置 Webhook URL 的渠道列表。返回 [(channel_name, url), ...]。"""
    result = []
    for ch_name, config_key in _CHANNEL_CONFIGS:
        url = cfg.get(config_key, "")
        if url:
            result.append((ch_name, url))
    return result


def _build_markdown(
    standard_number: str,
    std_name: str,
    implement_date: str,
    days_before: int,
) -> str:
    """构建通用 Markdown 消息体。"""
    if days_before == 0:
        days_label = "**今天**"
    elif days_before == 1:
        days_label = "**明天**"
    else:
        days_label = f"**{days_before} 天后**"

    return (
        f"## 标准实施日期提醒\n\n"
        f"**标准号**：{standard_number}\n"
        f"**标准名称**：{std_name}\n"
        f"**实施日期**：{implement_date}\n"
        f"**提醒**：该标准将于 {days_label} 实施，请及时处理。\n\n"
        f"---\n来自 PilotStd 标准管理系统"
    )


def _post_webhook(url: str, channel: str, content: str) -> bool:
    """向 Webhook URL 发送消息。返回 True 表示成功。"""
    try:
        if channel == "feishu":
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {"title": {"content": "标准日期提醒", "tag": "plain_text"}},
                    "elements": [{"tag": "markdown", "content": content}],
                },
            }
        else:
            payload = {"msgtype": "markdown", "markdown": {"content": content}}

        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True
        logger.warning("Webhook 返回非 200: channel=%s status=%d body=%s", channel, resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.error("Webhook 发送失败: channel=%s, %s", channel, e)
        return False


def _already_notified(db: Database, user_id: int, record_id: int, remind_type: str, days_before: int) -> bool:
    cursor = db.execute(
        "SELECT 1 FROM date_reminder_log WHERE user_id=? AND record_id=? AND remind_type=? AND days_before=? LIMIT 1",
        (user_id, record_id, remind_type, days_before),
    )
    return cursor.fetchone() is not None


def _mark_notified(db: Database, user_id: int, record_id: int, remind_type: str, days_before: int) -> None:
    db.execute(
        "INSERT INTO date_reminder_log (user_id, record_id, remind_type, days_before, sent_at)"
        " VALUES (?, ?, ?, ?, datetime('now'))",
        (user_id, record_id, remind_type, days_before),
    )


def _process_record(rec: dict, today: date, webhook_urls: list, db: Database, stats: dict) -> None:
    """处理单条记录：查收藏用户 → 检查去重 → 发送 Webhook → 记录日志。"""
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

    content = _build_markdown(rec["standard_number"], rec["std_name"] or "", impl_date, days_before)

    for user_id in user_ids:
        if _already_notified(db, user_id, record_id, "implement", days_before):
            stats["skipped"] += 1
            continue
        ok = any(_post_webhook(url, ch, content) for ch, url in webhook_urls)
        _mark_notified(db, user_id, record_id, "implement", days_before)
        if ok:
            stats["sent"] += 1
        else:
            stats["errors"] += 1


def run_date_reminder() -> dict[str, Any]:
    """日期提醒主任务。返回执行统计。"""
    db: Optional[Database] = None
    stats: dict[str, Any] = {"scanned": 0, "sent": 0, "skipped": 0, "errors": 0}
    try:
        cfg = ConfigManager()
        webhook_urls = _get_webhook_urls(cfg)
        if not webhook_urls:
            logger.info("日期提醒: 无已配置的 Webhook 渠道，跳过")
            return stats

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
            logger.info("日期提醒: 无到期标准")
            return stats

        for rec in records:
            _process_record(rec, today, webhook_urls, db, stats)

        logger.info(
            "日期提醒完成: scanned=%d sent=%d skipped=%d errors=%d",
            stats["scanned"],
            stats["sent"],
            stats["skipped"],
            stats["errors"],
        )
    except Exception as e:
        logger.error("日期提醒失败: %s", e, exc_info=True)
    finally:
        if db:
            db.close()
    return stats
