# docker/api/notification.py — 通知配置与发送日志 API
import logging

from fastapi import Depends
from fastapi.routing import APIRouter

from pilotstd.core.notification import NotificationManager, NotificationMessage

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notification"])


def _get_notification_mgr(mgr=Depends(get_manager_dep)) -> NotificationManager:
    return mgr.notification_mgr


@router.get("/api/notification/config")
def get_config(mgr=Depends(get_manager_dep)):
    """读取通知配置。"""
    cfg = mgr.cfg
    return {
        "enabled": cfg.get("notification.enabled", False),
        "channels": {
            "wechat": {
                "enabled": cfg.get("notification.channels.wechat.enabled", True),
                "webhook_url": "***" if cfg.get("notification.channels.wechat.webhook_url") else "",
            },
            "telegram": {
                "enabled": cfg.get("notification.channels.telegram.enabled", False),
                "bot_token": "***" if cfg.get("notification.channels.telegram.bot_token") else "",
                "chat_id": cfg.get("notification.channels.telegram.chat_id", ""),
            },
            "feishu": {
                "enabled": cfg.get("notification.channels.feishu.enabled", False),
                "webhook_url": "***" if cfg.get("notification.channels.feishu.webhook_url") else "",
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
    """更新通知配置。"""
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
    # 重新初始化渠道
    mgr._init_notification()
    return {"ok": True}


@router.post("/api/notification/test")
def test_notification(body: dict, nmgr=Depends(_get_notification_mgr)):
    """发送测试通知到指定渠道。body: {channel, title, body}"""
    channel = body.get("channel", "")
    msg = NotificationMessage(
        title=body.get("title", "测试通知"),
        body=body.get("body", "这是一条测试消息"),
        level="info",
        event_type="test",
    )
    result = nmgr.test_send(channel, msg)
    return result


@router.get("/api/notification/logs")
def get_logs(limit: int = 50, offset: int = 0, nmgr=Depends(_get_notification_mgr)):
    """查询通知发送日志（分页）。"""
    logs = nmgr.get_logs(limit=limit, offset=offset)
    return {"total": len(logs), "items": logs}
