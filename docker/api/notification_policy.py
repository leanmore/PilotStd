# 容器//脚本—通知策略接口（步 C：按职责自 notification.py 拆出）
"""通知策略接口：GET/PUT `/api/notification/policy`。

**端点路径与请求/响应 schema 与拆分前逐字一致**（约束 D-1/D-2）；本模块只做搬迁，不改逻辑。
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pilotstd.i18n import t

from .notification_deps import _get_notification_mgr, _get_user_id

logger = logging.getLogger(__name__)
# tags 由聚合模块 `notification.py` 在 include_router 时注入——
# 若此处也声明，同一路由会带上两个同名标签（OpenAPI 不再与拆分前一致）。
router = APIRouter()


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
        logger.exception(t("notification.api.log_get_policy_failed"))
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
        logger.exception(t("notification.api.log_save_policy_failed"))
        return JSONResponse({"error": str(e)}, status_code=500)
