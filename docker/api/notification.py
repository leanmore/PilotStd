# 容器//脚本—通知配置与发送日志接口（2：四渠道全参数）
import logging

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.notification import NotificationManager, NotificationMessage
from pilotstd.core.notification.events import ALL_EVENT_KEYS

from ..auth import get_current_user_id
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notification"])

# SEC-001: 本模块 9 个接口移除 @require_role —— 通知是用户级功能，
# 认证由 AuthMiddleware 保证，用户间隔离通过 user_id=Depends(_get_user_id)。

# ════════════════════════════════════════════════════════════════ 分隔
# 辅助函数：用户提取+通知管理器获取
# ════════════════════════════════════════════════════════════════ 分隔


def _get_user_id(username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)) -> int:
    """从 token 提取 user_id，找不到时返回 1（兼容系统调用）。"""
    user_id = mgr.user_service.get_user_id(username)
    return user_id if user_id is not None else 1


class MarkReadRequest(BaseModel):
    id: int | None = None  # None 表示全部标记已读


def _get_notification_mgr(mgr=Depends(get_manager_dep)) -> NotificationManager:
    return mgr.notification_mgr


@router.get("/api/notification/config")
def get_config(request: Request, mgr=Depends(get_manager_dep), user_id: int = Depends(_get_user_id)):
    """读取当前用户的渠道凭证配置。"""
    nmgr = mgr.notification_mgr
    creds: dict[str, dict[str, str]] = {}
    if nmgr._cred_helper:
        creds = nmgr._cred_helper.get_all(user_id)

    def mask(v: str) -> str:
        return "***" if v else ""

    # 构建每个渠道的配置视图，敏感字段（_等）做掩码处理
    def build_channel(ch_name: str, defaults: dict) -> dict:
        """构建单个渠道的配置视图：合并用户凭证与默认参数，敏感字段做掩码处理。"""
        ch = creds.get(ch_name) or {}
        result: dict[str, object] = {}
        for k in defaults:
            val = ch.get(k, "")
            if k in ("webhook_url", "bot_token", "secret", "corpsecret"):
                result[k] = mask(str(val))
            elif k == "enabled":
                if isinstance(val, bool):
                    result[k] = val
                elif isinstance(val, str) and val.lower() in ("false", "0", ""):
                    result[k] = False
                else:
                    result[k] = bool(val)
            else:
                result[k] = str(val)
        return result

    return {
        "enabled": mgr.cfg.get("notification.enabled", False),
        # 四渠道配置：///
        "channels": {
            "wechat": build_channel(
                "wechat",
                {
                    "enabled": True,
                    "webhook_url": "",
                    "corpid": "",
                    "agentid": "",
                    "corpsecret": "",
                    "proxy_url": "",
                },
            ),
            "telegram": build_channel("telegram", {"enabled": False, "bot_token": "", "chat_id": ""}),
            "feishu": build_channel("feishu", {"enabled": False, "webhook_url": "", "secret": ""}),
            "dingtalk": build_channel("dingtalk", {"enabled": False, "webhook_url": "", "secret": ""}),
        },
        "rules": {ev: mgr.cfg.get(f"notification.rules.{ev}", []) for ev in ALL_EVENT_KEYS},
    }


@router.put("/api/notification/config")
def update_config(
    request: Request,
    body: dict,
    mgr=Depends(get_manager_dep),
    user_id: int = Depends(_get_user_id),
):
    """更新通知配置（按用户隔离）。"""
    nmgr = mgr.notification_mgr
    for key, value in body.items():
        if key == "enabled":
            mgr.cfg.set("notification.enabled", bool(value))
        elif key == "channels":
            for ch_name, ch_cfg in value.items():
                if isinstance(ch_cfg, dict) and nmgr._cred_helper:
                    cleaned: dict[str, str] = {}
                    for k, v in ch_cfg.items():
                        if k == "enabled":
                            cleaned[k] = "true" if v else "false"
                        elif v:
                            cleaned[k] = str(v)
                    if cleaned:
                        nmgr._cred_helper.set_channel(user_id, ch_name, cleaned)
        elif key == "rules":
            for rule_name, channels in value.items():
                mgr.cfg.set(f"notification.rules.{rule_name}", channels)
    mgr.cfg.save()
    mgr._init_notification()
    return {"ok": True}


@router.post("/api/notification/test")
def test_notification(request: Request, body: dict, nmgr=Depends(_get_notification_mgr)):
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
    # 渠道参数覆盖（如测试前端的临时_）
    params = body.get("params") or {}
    result = nmgr.test_send(channel, msg, params)
    return result


@router.get("/api/notification/logs")
def get_logs(
    request: Request,
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
            # 验证存在
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
def get_unread_count(request: Request, nmgr=Depends(_get_notification_mgr)):
    """获取未读通知数量。"""
    try:
        count = nmgr.get_unread_count()
        return {"count": count}
    except Exception as e:
        logger.exception("获取未读数量失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/notification/logs")
def delete_notification_logs(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    nmgr=Depends(_get_notification_mgr),
):
    """清理通知日志（仅管理员）。删除 days 天前的记录。"""
    try:
        deleted = nmgr.cleanup_logs(days)
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.exception("清理通知日志失败")
        return JSONResponse({"error": str(e)}, status_code=500)


# ──通知策略接口──


class PolicyUpdateRequest(BaseModel):
    """通知策略更新请求体：渠道名、启用状态和订阅事件列表。"""

    channel: str
    enabled: bool | None = None
    events: list[str] | None = None


@router.get("/api/notification/policy")
def get_policy(request: Request, nmgr=Depends(_get_notification_mgr), user_id: int = Depends(_get_user_id)):
    """获取通知策略配置（渠道事件订阅，按用户隔离）。"""
    try:
        policies = nmgr.get_policies(user_id)
        return {"policies": policies}
    except Exception as e:
        logger.exception("获取通知策略失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/api/notification/policy")
def put_policy(
    request: Request,
    data: PolicyUpdateRequest,
    nmgr=Depends(_get_notification_mgr),
    user_id: int = Depends(_get_user_id),
):
    """更新通知策略（仅管理员，按用户隔离）。"""
    try:
        nmgr.save_policy(user_id, data.channel, data.enabled, data.events)
        return {"ok": True}
    except Exception as e:
        logger.exception("保存通知策略失败")
        return JSONResponse({"error": str(e)}, status_code=500)
