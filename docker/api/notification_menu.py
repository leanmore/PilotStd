"""通知渠道菜单管理 API（管理员）。

- `GET /api/notification/menu/status`：只读状态（不访问渠道网络）
- `PUT /api/notification/menu/config`：写渠道菜单配置（2026-11-21 补，见 A-27）
- `POST /api/notification/menu/sync?channel=...`：读配置 → 幂等同步 → 审计

真实渠道写入需要自建应用/机器人凭据；同步失败返回 400 + 可读原因。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from pilotstd.core.audit import write_audit
from pilotstd.core.config import ConfigManager
from pilotstd.core.notification.menu.config import menu_from_config
from pilotstd.core.notification.menu.service import MENU_CHANNELS, menu_status, sync_channel

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


class MenuConfigUpdate(BaseModel):
    """菜单配置写入请求：渠道 + 是否启用 + 菜单项（+ 飞书群标识）。"""

    channel: str
    enabled: bool = False
    items: list[dict] = []
    chat_id: str = ""


class MenuConfigResponse(BaseModel):
    """保存结果：渠道、是否启用、结构校验后的条目数。"""

    ok: bool
    channel: str
    enabled: bool
    items: int


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
    # 读取配置 → 幂等 `diff` → 渠道写入；结果只暴露状态/错误码，不回传凭据
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


# 配置写入口：校验结构/上限后再落库；钉钉与飞书有前置约束
@router.put("/api/notification/menu/config", response_model=MenuConfigResponse)
@require_role("admin")
def put_menu_config(request: Request, body: MenuConfigUpdate) -> MenuConfigResponse:
    """保存某渠道的菜单配置（结构校验失败 → 400，不落库）。"""
    channel = (body.channel or "").strip()
    if channel not in MENU_CHANNELS:
        raise HTTPException(status_code=400, detail=f"unknown channel: {channel}")
    # 钉钉机器人没有服务端持久菜单 API（见 docs/debt/02-accepted.md #9），不允许启用
    if channel == "dingtalk" and body.enabled:
        raise HTTPException(status_code=400, detail="dingtalk has no server-side menu API")
    if channel == "feishu" and body.enabled and not (body.chat_id or "").strip():
        raise HTTPException(status_code=400, detail="feishu menu requires chat_id")
    try:
        # 复用同一套校验（一级 ≤3、二级 ≤5、Telegram ≤3 命令、字段必填）
        menu = menu_from_config(
            channel, {"enabled": body.enabled, "items": body.items}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cfg = ConfigManager()
    cfg.set(f"notification.menus.{channel}.enabled", body.enabled)
    cfg.set(f"notification.menus.{channel}.items", body.items)
    if channel == "feishu":
        cfg.set("notification.menus.feishu.chat_id", (body.chat_id or "").strip())
    # 配置变化后清掉同步快照，让下一次 `sync` 真正下发
    cfg.set(f"notification.menus.{channel}.last_synced", None)
    cfg.save()
    try:
        write_audit(
            action="NOTIFICATION_MENU_CONFIG",
            resource=f"PUT /api/notification/menu/config?channel={channel}",
            detail={"channel": channel, "enabled": body.enabled, "items": len(menu.items)},
        )
    except Exception as e:  # 审计失败不改变保存结果，但必须可观测
        logger.error("notification menu config audit failed: %s", e, exc_info=True)
    return MenuConfigResponse(ok=True, channel=channel, enabled=body.enabled, items=len(menu.items))
