# docker/api/notification.py — 通知配置与发送日志 API（v2：四渠道全参数）
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.notification import NotificationManager, NotificationMessage

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notification"])


class MarkReadRequest(BaseModel):
    id: int | None = None  # None 表示全部标记已读


def _get_notification_mgr(mgr=Depends(get_manager_dep)) -> NotificationManager:
    return mgr.notification_mgr


@router.get("/api/notification/config")
def get_config(mgr=Depends(get_manager_dep)):
    """读取通知配置（四渠道全参数）。"""
    cfg = mgr.cfg

    def mask(v: str) -> str:
        return "***" if v else ""

    return {
        "enabled": cfg.get("notification.enabled", False),
        "channels": {
            "wechat": {
                "enabled": cfg.get("notification.channels.wechat.enabled", True),
                "webhook_url": mask(cfg.get("notification.channels.wechat.webhook_url", "")),
                "corpid": cfg.get("notification.channels.wechat.corpid", ""),
                "agentid": cfg.get("notification.channels.wechat.agentid", ""),
                "corpsecret": mask(cfg.get("notification.channels.wechat.corpsecret", "")),
                "proxy_url": cfg.get("notification.channels.wechat.proxy_url", ""),
            },
            "telegram": {
                "enabled": cfg.get("notification.channels.telegram.enabled", False),
                "bot_token": mask(cfg.get("notification.channels.telegram.bot_token", "")),
                "chat_id": cfg.get("notification.channels.telegram.chat_id", ""),
            },
            "feishu": {
                "enabled": cfg.get("notification.channels.feishu.enabled", False),
                "webhook_url": mask(cfg.get("notification.channels.feishu.webhook_url", "")),
                "secret": mask(cfg.get("notification.channels.feishu.secret", "")),
            },
            "dingtalk": {
                "enabled": cfg.get("notification.channels.dingtalk.enabled", False),
                "webhook_url": mask(cfg.get("notification.channels.dingtalk.webhook_url", "")),
                "secret": mask(cfg.get("notification.channels.dingtalk.secret", "")),
            },
        },
        "rules": {
            ev: cfg.get(f"notification.rules.{ev}", [])
            for ev in (
                "archive_complete",
                "standard_status_changed",
                "standard_expired",
                "standard_first_registered",
                "check_batch_complete",
            )
        },
    }


@router.put("/api/notification/config")
def update_config(body: dict, mgr=Depends(get_manager_dep)):
    """更新通知配置（四渠道全参数保存）。"""
    for key, value in body.items():
        if key == "enabled":
            mgr.cfg.set("notification.enabled", bool(value))
        elif key == "channels":
            for ch_name, ch_cfg in value.items():
                for ch_key, ch_val in ch_cfg.items():
                    mgr.cfg.set(f"notification.channels.{ch_name}.{ch_key}", ch_val)
        elif key == "rules":
            for rule_name, channels in value.items():
                mgr.cfg.set(f"notification.rules.{rule_name}", channels)
    mgr.cfg.save()
    mgr._init_notification()
    return {"ok": True}


@router.post("/api/notification/test")
def test_notification(body: dict, nmgr=Depends(_get_notification_mgr)):
    """发送测试通知到指定渠道。

    body:
      channel: str     — 渠道名: wechat / telegram / feishu / dingtalk
      title: str       — 标题（可选）
      body: str        — 正文（可选）
      params: dict     — 渠道参数覆盖（可选，如临时测试其他 webhook）
    """
    channel = body.get("channel", "")
    if channel not in ("wechat", "telegram", "feishu", "dingtalk"):
        return {"ok": False, "error": f"不支持的渠道: {channel}"}

    msg = NotificationMessage(
        title=body.get("title", "测试通知"),
        body=body.get("body", "这是一条测试消息"),
        level="info",
        event_type="test",
    )
    # 渠道参数覆盖（如测试前端的临时 webhook_url）
    params = body.get("params") or {}
    result = nmgr.test_send(channel, msg, params)
    return result


@router.get("/api/notification/logs")
def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: str | None = Query(None),
    status: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    is_read: bool | None = Query(None),
    nmgr=Depends(_get_notification_mgr),
):
    """查询通知发送日志（分页+筛选）。"""
    where_clauses: list[str] = []
    params: list = []

    if channel:
        where_clauses.append("channel = ?")
        params.append(channel)
    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if start_date:
        where_clauses.append("sent_at >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("sent_at <= ?")
        params.append(end_date + " 23:59:59")
    if is_read is not None:
        where_clauses.append("is_read = ?")
        params.append(1 if is_read else 0)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_row = nmgr._db.fetchone(
        f"SELECT COUNT(*) AS total FROM notification_log {where_sql}",
        tuple(params),
    )
    total = count_row["total"] if count_row else 0

    offset = (page - 1) * page_size
    rows = nmgr._db.fetchall(
        f"SELECT * FROM notification_log {where_sql} ORDER BY sent_at DESC LIMIT ? OFFSET ?",
        tuple(params + [page_size, offset]),
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "channel": r["channel"],
                "title": r["title"],
                "body": r["body"],
                "standard_number": r["standard_number"],
                "status": r["status"],
                "error_msg": r["error_msg"],
                "sent_at": r["sent_at"],
                "is_read": r.get("is_read", 0),
            }
            for r in rows
        ],
    }


@router.post("/api/notification/read")
def mark_notification_read(request: MarkReadRequest, nmgr=Depends(_get_notification_mgr)):
    """标记单条或全部通知为已读。id=None 表示全部标记已读。"""
    try:
        db = nmgr._db
        if request.id is not None:
            existing = db.fetchone("SELECT id FROM notification_log WHERE id=?", (request.id,))
            if not existing:
                return JSONResponse({"error": f"通知 ID {request.id} 不存在"}, status_code=404)
            db.execute("UPDATE notification_log SET is_read=1 WHERE id=?", (request.id,))
        else:
            db.execute("UPDATE notification_log SET is_read=1")
        db.commit()
        return {"ok": True, "message": "已标记为已读"}
    except Exception as e:
        logger.exception("标记已读失败")
        return JSONResponse({"error": str(e)}, status_code=500)
