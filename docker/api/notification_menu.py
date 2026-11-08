"""通知渠道菜单管理 API（管理员）。

- `GET /api/notification/menu/status`：只读状态（不访问渠道网络）
- `POST /api/notification/menu/sync?channel=...`：读配置 → 幂等同步 → 审计

真实渠道写入需要自建应用/机器人凭据；同步失败返回 400 + 可读原因。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from pilotstd.core.audit import write_audit
from pilotstd.core.config import ConfigManager
from pilotstd.core.notification.menu.service import menu_status, sync_channel

from ..auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notification-menu"])


# ── 响应模型（G-052/契约测试要求所有路由有 response_model）──
class MenuStatusItem(BaseModel):
    """单渠道菜单状态。"""

    channel: str
    supported: bool
    types: list[str]
    enabled: bool
    last_synced: dict | None = None


class MenuStatusResponse(BaseModel):
    """四渠道状态响应。"""

    channels: list[MenuStatusItem]


class MenuSyncResponse(BaseModel):
    """菜单同步结果。"""

    ok: bool
    channel: str
    changed: bool
    code: str = ""
    error: str = ""
    skipped: str = ""


@router.get("/api/notification/menu/status", response_model=MenuStatusResponse)
@require_role("admin")
def get_menu_status(request: Request) -> MenuStatusResponse:
    """返回四渠道菜单能力/启用状态/最后同步时间。"""
    return MenuStatusResponse(channels=[MenuStatusItem(**item) for item in menu_status(ConfigManager())])


# 同步端点：管理员触发；审计失败不影响同步结果，但必须可观测
@router.post("/api/notification/menu/sync", response_model=MenuSyncResponse)
@require_role("admin")
def sync_menu(request: Request, channel: str = Query(..., min_length=1)) -> MenuSyncResponse:
    """按渠道同步菜单；相同配置重复调用不写渠道接口。"""
    # 读取配置 → 幂等 diff → 渠道写入；结果只暴露状态/错误码，不回传凭据
    result = sync_channel(channel, ConfigManager())
    try:
        write_audit(
            action="NOTIFICATION_MENU_SYNC",
            resource=f"POST /api/notification/menu/sync?channel={channel}",
            detail={"channel": channel, "ok": result.get("ok"), "changed": result.get("changed")},
        )
    except Exception as e:  # 审计失败不改变同步结果，但必须可观测
        logger.error("notification menu audit failed: %s", e, exc_info=True)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "menu sync failed")
    return MenuSyncResponse(**result)
