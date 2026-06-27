# docker/api/wechat_ip.py — 企业微信可信 IP 自动更新 API
# GET  /api/wechat-ip/config   → 获取配置
# PUT  /api/wechat-ip/config   → 保存配置
# POST /api/wechat-ip/check    → 立即检测并更新
# GET  /api/wechat-ip/status   → 当前状态
import logging

from fastapi import Depends
from fastapi.routing import APIRouter

from pilotstd.wechat_ip.browser import validate_cookie
from pilotstd.wechat_ip.cookie_mgr import (
    decrypt_cookie,
    encrypt_cookie,
    mask_cookie,
)
from pilotstd.wechat_ip.detector import detect_ip
from pilotstd.wechat_ip.scheduler import (
    run_check,
)
from pilotstd.wechat_ip.scheduler import (
    start as start_scheduler,
)
from pilotstd.wechat_ip.scheduler import (
    stop as stop_scheduler,
)

from ..auth import require_admin
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wechat-ip"])

ENCRYPT_SECRET = "pilotstd_wework_ip_2026"


def _notify(mgr, title: str, body: str) -> None:
    """通过通知管理器发送系统通知。"""
    try:
        mgr.notification_mgr.send_event("trust_ip_update", {"title": title, "body": body})
    except Exception:
        pass


@router.get("/api/wechat-ip/config")
def get_config(mgr=Depends(get_manager_dep)):
    """获取可信 IP 自动更新配置。"""
    cfg = mgr.cfg
    encrypted = cfg.get("wechat_ip.encrypted_cookie", "")

    # 尝试解密显示 Cookie 状态
    cookie_status = "未配置"
    try:
        if encrypted:
            decrypted = decrypt_cookie(encrypted, ENCRYPT_SECRET)
            if decrypted:
                cookie_status = f"已配置 ({mask_cookie(decrypted)})"
    except Exception:
        cookie_status = "解密失败"

    return {
        "enabled": cfg.get("wechat_ip.enabled", False),
        "interval_hours": cfg.get("wechat_ip.interval_hours", 6),
        "ip_sources": cfg.get("wechat_ip.ip_sources", ["https://myip.ipip.net", "https://4.ipw.cn"]),
        "cookie_source": cfg.get("wechat_ip.cookie_source", "manual"),
        "cookiecloud_url": cfg.get("wechat_ip.cookiecloud_url", ""),
        "cookiecloud_key": cfg.get("wechat_ip.cookiecloud_key", ""),
        "cookiecloud_password": cfg.get("wechat_ip.cookiecloud_password", ""),
        "cookie_status": cookie_status,
        "app_urls": cfg.get("wechat_ip.app_urls", ""),
        "use_selenium": cfg.get("wechat_ip.use_selenium", True),
        "update_mode": cfg.get("wechat_ip.update_mode", "append"),
        "notify_result": cfg.get("wechat_ip.notify_result", True),
        "last_ip": cfg.get("wechat_ip.last_ip", ""),
        "last_check_at": cfg.get("wechat_ip.last_check_at", ""),
    }


@router.put("/api/wechat-ip/config")
def put_config(body: dict, mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """保存可信 IP 配置。"""
    cfg = mgr.cfg
    was_enabled = cfg.get("wechat_ip.enabled", False)

    # 布尔 + 字符串字段
    for key in (
        "enabled",
        "interval_hours",
        "cookie_source",
        "cookiecloud_url",
        "cookiecloud_key",
        "cookiecloud_password",
        "app_urls",
        "update_mode",
        "notify_result",
        "use_selenium",
    ):
        if key in body:
            cfg.set(f"wechat_ip.{key}", body[key])

    # IP 检测源（列表）
    if "ip_sources" in body:
        cfg.set("wechat_ip.ip_sources", body["ip_sources"])

    # Cookie 手动导入（加密存储）
    if "cookie_raw" in body and body["cookie_raw"]:
        raw = body["cookie_raw"].strip()
        encrypted = encrypt_cookie(raw, ENCRYPT_SECRET)
        cfg.set("wechat_ip.encrypted_cookie", encrypted)
        cfg.set("wechat_ip.cookie_source", "manual")
        logger.info("手动导入 Cookie: %s", mask_cookie(raw))

    cfg.save()

    # 启用/禁用定时检测
    now_enabled = cfg.get("wechat_ip.enabled", False)
    if now_enabled and not was_enabled:
        interval = int(cfg.get("wechat_ip.interval_hours", 6)) * 3600
        start_scheduler(cfg, interval, lambda t, b: _notify(mgr, t, b))
    elif not now_enabled and was_enabled:
        stop_scheduler()

    return {"ok": True}


@router.post("/api/wechat-ip/check")
def trigger_check(mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """立即执行一次 IP 检测 + 更新。"""
    cfg = mgr.cfg

    # 先确保 Cookie 可用
    if cfg.get("wechat_ip.cookie_source", "") == "cookiecloud":
        from pilotstd.wechat_ip.scheduler import _get_cookie

        _get_cookie(cfg)

    result = run_check(cfg, lambda t, b: _notify(mgr, t, b))
    cfg.set("wechat_ip.last_check_at", __import__("datetime").datetime.now().isoformat())
    cfg.save()
    return result


@router.get("/api/wechat-ip/status")
def get_status(mgr=Depends(get_manager_dep)):
    """获取当前状态：公网 IP、Cookie 有效性、上次更新结果。"""
    cfg = mgr.cfg
    now_ip = detect_ip()

    cookie_valid = False
    encrypted = cfg.get("wechat_ip.encrypted_cookie", "")
    if encrypted:
        try:
            decrypted = decrypt_cookie(encrypted, ENCRYPT_SECRET)
            cookie_valid = validate_cookie(decrypted, "")
        except Exception:
            pass

    return {
        "current_ip": now_ip or "未知",
        "last_ip": cfg.get("wechat_ip.last_ip", ""),
        "ip_changed": now_ip != cfg.get("wechat_ip.last_ip", "") if now_ip else False,
        "cookie_valid": cookie_valid,
        "enabled": cfg.get("wechat_ip.enabled", False),
        "last_check_at": cfg.get("wechat_ip.last_check_at", ""),
    }
