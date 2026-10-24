# 模块：项目/管理器/__服务脚本
# 微信检测服务—供接口层+脚本生命周期使用

from __future__ import annotations

import logging
import os
from typing import Any

from pilotstd.core.status import Status

logger = logging.getLogger(__name__)

# 可信 IP cookie 的加密密钥**不设可用默认值**：默认值一旦进 git 就等于公开密钥。
# 取值顺序：环境变量 > config 的 wechat_ip.encrypt_secret > 抛错（拒绝静默降级）。
_ENV_SECRET = "WECHAT_IP_ENCRYPT_SECRET"
_CFG_SECRET_KEY = "wechat_ip.encrypt_secret"


class WechatIPService:
    """企业微信可信 IP 检测服务（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def _get_secret(self) -> str:
        """Return the encryption secret; raise rather than use a public default."""
        # 取值顺序：环境变量 > config 同名字段 > 抛错（见模块级注释）
        env_secret = os.environ.get(_ENV_SECRET, "").strip()
        if env_secret:
            return env_secret
        cfg_secret = str(self._mgr.cfg.get(_CFG_SECRET_KEY, "") or "").strip()
        if cfg_secret:
            return cfg_secret
        raise RuntimeError(
            f"wechat_ip encrypt secret is not configured: set env {_ENV_SECRET} "
            f"(or config {_CFG_SECRET_KEY}). Refusing to fall back to a public default key."
        )

    def _notify(self, title: str, body: str, status: str = "info") -> None:
        """发送可信 IP 通知；`status` 为机器可读结果标记（T-39：级别不再由标题中文推断）。"""
        try:
            self._mgr.notification_mgr.send_event(
                "trust_ip_update", {"title": title, "body": body, "status": status}
            )
        except Exception as e:
            logger.warning("可信IP更新通知发送失败: %s", e)

    # ──接口端点方法─────────────────────────────────────────

    def get_config(self) -> dict[str, Any]:
        """获取可信 IP 配置（含 Cookie 状态）。"""
        from pilotstd.wechat_ip.cookie_mgr import decrypt_cookie, mask_cookie

        cfg = self._mgr.cfg
        encrypted = cfg.get("wechat_ip.encrypted_cookie", "")

        cookie_status = "未配置"
        try:
            if encrypted:
                decrypted = decrypt_cookie(encrypted, self._get_secret())
                if decrypted:
                    cookie_status = f"已配置 ({mask_cookie(decrypted)})"
        except RuntimeError:
            # 密钥缺失是配置问题，不是"解密失败"——两类状态要能区分
            # i18n-allow: 与同函数既有"未配置/已配置/解密失败"同属对前端的固定中文状态值，改动需前后端同批
            cookie_status = "未配置密钥"
        except Exception:
            cookie_status = "解密失败"

        return {
            "enabled": cfg.get("wechat_ip.enabled", False),
            "interval_hours": cfg.get("wechat_ip.interval_hours", 6),
            "ip_sources": cfg.get("wechat_ip.ip_sources", ["https://myip.ipip.net", "https://4.ipw.cn"]),
            "cookie_source": cfg.get("wechat_ip.cookie_source", "manual"),
            "cookiecloud_url": cfg.get("wechat_ip.cookiecloud_url", ""),
            "cookiecloud_key": "***" if cfg.get("wechat_ip.cookiecloud_key") else "",
            "cookiecloud_password": "***" if cfg.get("wechat_ip.cookiecloud_password") else "",
            "cookie_status": cookie_status,
            "app_urls": cfg.get("wechat_ip.app_urls", ""),
            "use_selenium": cfg.get("wechat_ip.use_selenium", True),
            "update_mode": cfg.get("wechat_ip.update_mode", "append"),
            "notify_result": cfg.get("wechat_ip.notify_result", True),
            "last_ip": cfg.get("wechat_ip.last_ip", ""),
            "last_check_at": cfg.get("wechat_ip.last_check_at", ""),
        }

    def update_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """更新可信 IP 配置，自动处理定时器启停。"""
        from pilotstd.wechat_ip.cookie_mgr import encrypt_cookie
        from pilotstd.wechat_ip.scheduler import start as start_scheduler
        from pilotstd.wechat_ip.scheduler import stop as stop_scheduler

        cfg = self._mgr.cfg
        was_enabled = cfg.get("wechat_ip.enabled", False)

        # 先校验密钥再改任何字段：失败时不留半套内存状态
        raw_cookie = str(body.get("cookie_raw") or "").strip()
        secret = ""
        if raw_cookie:
            try:
                secret = self._get_secret()
            except RuntimeError as e:
                logger.warning("wechat_ip config not saved: %s", e)
                return {"ok": False, "error": str(e)}

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

        if "ip_sources" in body:
            cfg.set("wechat_ip.ip_sources", body["ip_sources"])

        if raw_cookie:
            encrypted = encrypt_cookie(raw_cookie, secret)
            cfg.set("wechat_ip.encrypted_cookie", encrypted)
            cfg.set("wechat_ip.cookie_source", "manual")

        cfg.save()

        now_enabled = cfg.get("wechat_ip.enabled", False)
        if now_enabled and not was_enabled:
            interval = int(cfg.get("wechat_ip.interval_hours", 6)) * 3600
            start_scheduler(cfg, interval, lambda t, b, s: self._notify(t, b, s))
        elif not now_enabled and was_enabled:
            stop_scheduler()

        return {"ok": True}

    def run_check(self) -> dict[str, Any]:
        """执行一次 IP 检测 + 更新。"""
        from datetime import datetime

        from pilotstd.wechat_ip.scheduler import _get_cookie, run_check

        cfg = self._mgr.cfg

        if cfg.get("wechat_ip.cookie_source", "") == "cookiecloud":
            _get_cookie(cfg)

        result = run_check(cfg, lambda t, b, s: self._notify(t, b, s))
        cfg.set("wechat_ip.last_check_at", datetime.now().isoformat())
        cfg.save()
        return result

    def get_status(self) -> dict[str, Any]:
        """获取当前状态：公网 IP、Cookie 有效性、上次更新结果。"""
        from pilotstd.wechat_ip.browser import validate_cookie
        from pilotstd.wechat_ip.cookie_mgr import decrypt_cookie
        from pilotstd.wechat_ip.detector import detect_ip

        cfg = self._mgr.cfg
        now_ip = detect_ip()

        cookie_valid = False
        encrypted = cfg.get("wechat_ip.encrypted_cookie", "")
        if encrypted:
            try:
                decrypted = decrypt_cookie(encrypted, self._get_secret())
                cookie_valid = validate_cookie(decrypted, "")
            except Exception as e:
                # 解密/校验失败 → cookie_valid 保持 False，但必须留痕
                logger.warning("wechat_ip cookie decrypt/validate failed: %s", e)

        return {
            "current_ip": now_ip or Status.UNKNOWN.value,
            # 前端据此判定标签样式（不再比较中文文案 '未知'——#32-C / R14-4c）
            "current_ip_known": bool(now_ip),
            "last_ip": cfg.get("wechat_ip.last_ip", ""),
            "ip_changed": now_ip != cfg.get("wechat_ip.last_ip", "") if now_ip else False,
            "cookie_valid": cookie_valid,
            "enabled": cfg.get("wechat_ip.enabled", False),
            "last_check_at": cfg.get("wechat_ip.last_check_at", ""),
        }

    # ──脚本生命周期专用─────────────────────────────────

    def start_scheduler(self) -> None:
        """启动定时检测线程（app.py lifespan 用）。"""
        from pilotstd.wechat_ip.scheduler import start as start_scheduler

        cfg = self._mgr.cfg
        interval = int(cfg.get("wechat_ip.interval_hours", 6)) * 3600
        start_scheduler(cfg, interval, lambda t, b, s: self._notify(t, b, s))

    def stop_scheduler(self) -> None:
        """停止定时检测线程（app.py lifespan 用）。"""
        from pilotstd.wechat_ip.scheduler import stop as stop_scheduler

        stop_scheduler()
