# 模块：项目/管理器/__服务脚本
# 微信检测服务—供接口层+脚本生命周期使用

from __future__ import annotations

from typing import Any

_DEFAULT_ENCRYPT_SECRET = "pilotstd_wework_ip_2026"


class WechatIPService:
    """企业微信可信 IP 检测服务（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def _get_secret(self) -> str:
        cfg = self._mgr.cfg
        return cfg.get("wechat_ip.encrypt_secret") or _DEFAULT_ENCRYPT_SECRET

    def _notify(self, title: str, body: str) -> None:
        try:
            self._mgr.notification_mgr.send_event("trust_ip_update", {"title": title, "body": body})
        except Exception:
            pass

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

        if "cookie_raw" in body and body["cookie_raw"]:
            raw = body["cookie_raw"].strip()
            encrypted = encrypt_cookie(raw, self._get_secret())
            cfg.set("wechat_ip.encrypted_cookie", encrypted)
            cfg.set("wechat_ip.cookie_source", "manual")

        cfg.save()

        now_enabled = cfg.get("wechat_ip.enabled", False)
        if now_enabled and not was_enabled:
            interval = int(cfg.get("wechat_ip.interval_hours", 6)) * 3600
            start_scheduler(cfg, interval, lambda t, b: self._notify(t, b))
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

        result = run_check(cfg, lambda t, b: self._notify(t, b))
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

    # ──脚本生命周期专用─────────────────────────────────

    def start_scheduler(self) -> None:
        """启动定时检测线程（app.py lifespan 用）。"""
        from pilotstd.wechat_ip.scheduler import start as start_scheduler

        cfg = self._mgr.cfg
        interval = int(cfg.get("wechat_ip.interval_hours", 6)) * 3600
        start_scheduler(cfg, interval, lambda t, b: self._notify(t, b))

    def stop_scheduler(self) -> None:
        """停止定时检测线程（app.py lifespan 用）。"""
        from pilotstd.wechat_ip.scheduler import stop as stop_scheduler

        stop_scheduler()
