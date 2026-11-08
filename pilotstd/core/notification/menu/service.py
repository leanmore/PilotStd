"""菜单客户端工厂与同步服务（渠道无关）。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database
from pilotstd.core.notification._credentials import SYSTEM_DEFAULT_USER_ID, CredentialHelper

from .clients import (
    DingtalkMenuClient,
    FeishuMenuClient,
    MenuClient,
    TelegramCommandClient,
    WecomMenuClient,
    _http_json,
)
from .config import load_menu
from .model import menu_to_dict

logger = logging.getLogger(__name__)
MENU_CHANNELS = ("wechat", "feishu", "telegram", "dingtalk")


# 渠道基础配置（config.json）；DB 凭证随后覆盖同名字段
def _config_channel(cfg: Any, channel: str) -> dict[str, Any]:
    raw = cfg.get(f"notification.channels.{channel}") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def _credentials(channel: str) -> dict[str, Any]:
    """读系统默认用户的渠道凭证；DB/配置不可用时降级为空。"""
    try:
        db = Database(get_db_path())
        helper = CredentialHelper(db, str(Path(get_db_path()).parent))
        return helper.get_channel(SYSTEM_DEFAULT_USER_ID, channel) or {}
    except Exception as e:  # pragma: no cover - 部署环境/测试替身差异
        # 凭证读取失败不是静默路径：用 warning 留下可观测信号，由调用方报“未配置”
        logger.warning("read menu credentials failed: %s", e)
        return {}


# 客户端工厂：测试可注入 transport；未知渠道落到钉钉 unsupported 客户端
def build_client(channel: str, cfg: Any, *, transport=_http_json) -> MenuClient:
    """按渠道构造客户端；凭据合并顺序：config 基础字段 → DB 凭证覆盖。"""
    base = _config_channel(cfg, channel)
    base.update(_credentials(channel))
    if channel == "wechat":
        return WecomMenuClient(
            str(base.get("corpid") or ""),
            str(base.get("corpsecret") or ""),
            str(base.get("agentid") or ""),
            transport=transport,
            proxy_url=str(base.get("proxy_url") or ""),
        )
    if channel == "feishu":
        return FeishuMenuClient(
            str(base.get("app_id") or ""),
            str(base.get("app_secret") or ""),
            str(cfg.get("notification.menus.feishu.chat_id") or ""),
            transport=transport,
        )
    if channel == "telegram":
        return TelegramCommandClient(str(base.get("bot_token") or ""), transport=transport)
    return DingtalkMenuClient()


# 同步：先读线上菜单，只有 last_synced 与期望不同才调用写接口
def sync_channel(channel: str, cfg: Any, *, transport=_http_json) -> dict[str, Any]:
    """幂等同步：配置与 `last_synced` 相同且线上可读时跳过写接口。"""
    if channel not in MENU_CHANNELS:
        return {"ok": False, "channel": channel, "changed": False, "error": "unknown channel"}
    menu = load_menu(channel, cfg)
    if not menu.enabled:
        return {"ok": True, "channel": channel, "changed": False, "skipped": "disabled"}
    client = build_client(channel, cfg, transport=transport)
    if not client.supports_menu():
        return {
            "ok": False,
            "channel": channel,
            "changed": False,
            "error": "channel menu capability is not configured",
        }
    desired = menu_to_dict(menu)
    last = cfg.get(f"notification.menus.{channel}.last_synced")
    current = client.get_menu()
    if last == desired and current.ok:
        return {"ok": True, "channel": channel, "changed": False}
    result = client.create_menu(menu)
    if result.ok:
        cfg.set(f"notification.menus.{channel}.last_synced", desired)
        cfg.save()
    return {
        "ok": result.ok,
        "channel": channel,
        "changed": result.ok,
        "code": result.code,
        "error": result.message,
    }


# 状态只读：不发起渠道网络请求，供管理页/排障先看配置
def menu_status(cfg: Any) -> list[dict[str, Any]]:
    """只读状态：不访问渠道网络接口。"""
    out = []
    for channel in MENU_CHANNELS:
        client = build_client(channel, cfg)
        out.append(
            {
                "channel": channel,
                "supported": client.supports_menu(),
                "types": sorted(t for t in ("view", "click", "command", "group") if client.supports_type(t)),
                "enabled": bool((cfg.get(f"notification.menus.{channel}") or {}).get("enabled", False)),
                "last_synced": cfg.get(f"notification.menus.{channel}.last_synced"),
            }
        )
    return out
