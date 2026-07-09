# docker/api/notification.py — 通知配置与发送日志 API（v2：四渠道全参数）
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.notification import NotificationManager, NotificationMessage
from pilotstd.core.notification.events import ALL_EVENT_KEYS

from ..auth import require_admin
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
        "rules": {ev: cfg.get(f"notification.rules.{ev}", []) for ev in ALL_EVENT_KEYS},
    }


@router.put("/api/notification/config")
def update_config(body: dict, mgr=Depends(get_manager_dep), _: bool = Depends(require_admin)):
    """更新通知配置（仅管理员）。"""
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
    result = nmgr.get_logs(
        page=page,
        size=page_size,
        channel=channel,
        status=status,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
    )
    return {
        "total": result["total"],
        "page": result["page"],
        "page_size": result["size"],
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
            for r in result["items"]
        ],
    }


@router.post("/api/notification/read")
def mark_notification_read(request: MarkReadRequest, nmgr=Depends(_get_notification_mgr)):
    """标记单条或全部通知为已读。id=None 表示全部标记已读。"""
    try:
        ids = [request.id] if request.id is not None else None
        if request.id is not None:
            # 验证 ID 存在
            result = nmgr.get_logs(page=1, size=1, start_date=None, end_date=None)
            existing_ids = {r["id"] for r in result["items"]}
            if request.id not in existing_ids:
                return JSONResponse({"error": f"通知 ID {request.id} 不存在"}, status_code=404)
        count = nmgr.mark_logs_read(ids)
        return {"ok": True, "count": count, "message": "已标记为已读"}
    except Exception as e:
        logger.exception("标记已读失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/notification/unread-count")
def get_unread_count(nmgr=Depends(_get_notification_mgr)):
    """获取未读通知数量。"""
    try:
        count = nmgr.get_unread_count()
        return {"count": count}
    except Exception as e:
        logger.exception("获取未读数量失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/notification/logs")
def delete_notification_logs(
    days: int = Query(30, ge=1, le=365),
    nmgr=Depends(_get_notification_mgr),
    _: str = Depends(require_admin),
):
    """清理通知日志（仅管理员）。删除 days 天前的记录。"""
    try:
        deleted = nmgr.cleanup_logs(days)
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.exception("清理通知日志失败")
        return JSONResponse({"error": str(e)}, status_code=500)


# ── 通知策略 API ──


class PolicyUpdateRequest(BaseModel):
    channel: str
    enabled: bool | None = None
    events: list[str] | None = None


@router.get("/api/notification/policy")
def get_policy(nmgr=Depends(_get_notification_mgr)):
    """获取通知策略配置（渠道事件订阅）。"""
    try:
        policies = nmgr.get_policies()
        return {"policies": policies}
    except Exception as e:
        logger.exception("获取通知策略失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/api/notification/policy")
def put_policy(
    data: PolicyUpdateRequest,
    nmgr=Depends(_get_notification_mgr),
    _: str = Depends(require_admin),
):
    """更新通知策略（仅管理员）。"""
    try:
        nmgr.save_policy(data.channel, data.enabled, data.events)
        return {"ok": True}
    except Exception as e:
        logger.exception("保存通知策略失败")
        return JSONResponse({"error": str(e)}, status_code=500)
