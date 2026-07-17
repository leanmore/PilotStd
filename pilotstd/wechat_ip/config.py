# pilotstd/wechat_ip/config.py
"""可信 IP 更新配置模型。"""

from dataclasses import dataclass


@dataclass
class WechatIPConfig:
    """企业微信可信 IP 配置。"""

    enabled: bool = False
    interval_hours: int = 6
    app_urls: str = ""  # 逗号分隔的多个应用管理 URL
    mode: str = "append"  # append | replace
    cookie_source: str = "cookiecloud"  # cookiecloud | manual
    cookiecloud_server: str = ""
    cookiecloud_user_key: str = ""
    cookiecloud_password: str = ""
    manual_cookie_encrypted: str = ""
    encrypt_secret: str = "pilotstd_wework_ip_2026"
    notify_result: bool = True
    headless: bool = True
    engine: str = "auto"  # auto | cloakbrowser | playwright
    last_ip: str = ""
    last_check_at: str = ""


# 配置 ↔ 字典互转（与 pilotstd 配置系统集成）
def from_config_dict(data: dict) -> WechatIPConfig:
    """从配置字典加载。"""
    return WechatIPConfig(
        enabled=data.get("wechat_ip.enabled", False),
        interval_hours=int(data.get("wechat_ip.interval_hours", 6)),
        app_urls=data.get("wechat_ip.app_urls", ""),
        mode=data.get("wechat_ip.update_mode", "append"),
        cookie_source=data.get("wechat_ip.cookie_source", "cookiecloud"),
        cookiecloud_server=data.get("wechat_ip.cookiecloud_url", ""),
        cookiecloud_user_key=data.get("wechat_ip.cookiecloud_key", ""),
        cookiecloud_password=data.get("wechat_ip.cookiecloud_password", ""),
        manual_cookie_encrypted=data.get("wechat_ip.encrypted_cookie", ""),
        encrypt_secret=data.get("wechat_ip.encrypt_secret", "pilotstd_wework_ip_2026"),
        notify_result=data.get("wechat_ip.notify_result", True),
        headless=data.get("wechat_ip.headless", True),
        engine=data.get("wechat_ip.engine", "auto"),
        last_ip=data.get("wechat_ip.last_ip", ""),
        last_check_at=data.get("wechat_ip.last_check_at", ""),
    )


def to_config_dict(cfg: WechatIPConfig) -> dict:
    """转为配置字典。"""
    return {
        "wechat_ip.enabled": cfg.enabled,
        "wechat_ip.interval_hours": cfg.interval_hours,
        "wechat_ip.app_urls": cfg.app_urls,
        "wechat_ip.update_mode": cfg.mode,
        "wechat_ip.cookie_source": cfg.cookie_source,
        "wechat_ip.cookiecloud_url": cfg.cookiecloud_server,
        "wechat_ip.cookiecloud_key": cfg.cookiecloud_user_key,
        "wechat_ip.cookiecloud_password": cfg.cookiecloud_password,
        "wechat_ip.encrypted_cookie": cfg.manual_cookie_encrypted,
        "wechat_ip.encrypt_secret": cfg.encrypt_secret,
        "wechat_ip.notify_result": cfg.notify_result,
        "wechat_ip.headless": cfg.headless,
        "wechat_ip.engine": cfg.engine,
        "wechat_ip.last_ip": cfg.last_ip,
        "wechat_ip.last_check_at": cfg.last_check_at,
    }
