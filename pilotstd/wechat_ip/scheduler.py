# pilotstd/wechat_ip/scheduler.py
# pragma: no cover — 需浏览器环境，暂不纳入单元测试覆盖率考核
# 详见 docs/testing/known-issues.md
"""可信 IP 定时更新调度器。使用 daemon 线程定期检测 IP 变化。"""

import logging
import threading
from typing import Any, Callable, Optional

from .browser import BrowserError, WechatIPUpdater
from .cookie_mgr import decrypt_cookie, encrypt_cookie, fetch_cookiecloud, mask_cookie
from .detector import detect_ip as do_detect_ip

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 6 * 3600
_check_thread: Optional[threading.Thread] = None
_stop = threading.Event()


def run_check(config: Any, notify_cb: Optional[Callable] = None) -> dict:
    """执行一次 IP 检测 + 更新流程。返回结果字典。"""
    result = {"ip": "", "changed": False, "updated": False, "error": ""}

    # 1. 检测 IP
    ip = do_detect_ip()
    if not ip:
        result["error"] = "IP 检测失败"
        _notify(notify_cb, "IP 检测失败", "所有检测源均不可用")
        return result
    result["ip"] = ip

    # 2. 对比
    last_ip = config.get("wechat_ip.last_ip", "")
    if ip == last_ip:
        return result
    result["changed"] = True
    logger.info("IP 变化: %s → %s", last_ip, ip)

    # 3. 获取 Cookie
    cookie = _get_cookie(config)
    if not cookie:
        result["error"] = "无法获取 Cookie"
        _notify(notify_cb, "IP 更新失败", "无法获取企业微信 Cookie")
        return result

    # 4. 获取应用列表
    urls_str = config.get("wechat_ip.app_urls", "")
    app_urls = [u.strip() for u in urls_str.split(",") if u.strip()]
    if not app_urls:
        result["error"] = "未配置应用管理地址"
        return result

    # 5. 更新
    mode = config.get("wechat_ip.update_mode", "append")
    engine = config.get("wechat_ip.engine", "auto")
    headless = config.get("wechat_ip.headless", True)
    cache_dir = config.get("wechat_ip.cache_dir", "/app/browser_cache")

    try:
        updater = WechatIPUpdater(headless=headless, cache_dir=cache_dir, engine=engine)
        results = updater.update_multiple(app_urls, ip, cookie, mode)
        ok = all(results.values()) and len(results) > 0
        result["updated"] = ok

        if ok:
            config.set("wechat_ip.last_ip", ip)
            config.save()
            _notify(notify_cb, "可信 IP 已更新", f"公网 IP 已变更为 {ip}")
        else:
            failed = [u for u, v in results.items() if not v]
            _notify(notify_cb, "IP 更新部分失败", f"失败: {', '.join(failed[:3])}")
    except BrowserError as e:
        result["error"] = str(e)
        _notify(notify_cb, "IP 更新失败", str(e))

    return result


def _get_cookie(config: Any) -> Optional[str]:
    """获取 Cookie：CookieCloud > 手动导入。"""
    if config.get("wechat_ip.cookie_source", "") == "cookiecloud":
        url = config.get("wechat_ip.cookiecloud_url", "")
        key = config.get("wechat_ip.cookiecloud_key", "")
        pwd = config.get("wechat_ip.cookiecloud_password", "")
        if url and key:
            cookie = fetch_cookiecloud(url, key, pwd)
            if cookie:
                logger.info("CookieCloud: %s", mask_cookie(cookie))
                # 加密缓存到本地
                secret = config.get("wechat_ip.encrypt_secret", "pilotstd_wework_ip_2026")
                config.set("wechat_ip.encrypted_cookie", encrypt_cookie(cookie, secret))
                config.save()
                return cookie

    encrypted = config.get("wechat_ip.encrypted_cookie", "")
    if encrypted:
        secret = config.get("wechat_ip.encrypt_secret", "pilotstd_wework_ip_2026")
        try:
            return decrypt_cookie(encrypted, secret)
        except Exception as e:
            logger.warning("Cookie 解密失败: %s", e)
    return None


def _notify(cb: Optional[Callable], title: str, body: str) -> None:
    """安全调用通知回调，异常静默丢弃。"""
    if cb:
        try:
            cb(title, body)
        except Exception:
            pass


def start(config: Any, interval: int = DEFAULT_INTERVAL, notify_cb: Optional[Callable] = None):
    """启动定时检测线程。"""
    global _check_thread, _stop
    if _check_thread and _check_thread.is_alive():
        return
    _stop.clear()

    def loop():
        """定时检测主循环：先立即执行一次，之后按间隔周期执行。"""
        logger.info("可信 IP 定时检测已启动 (间隔=%ds)", interval)
        try:
            run_check(config, notify_cb)
        except Exception:
            logger.exception("初始检测失败")
        while not _stop.wait(interval):
            try:
                run_check(config, notify_cb)
            except Exception:
                logger.exception("定时检测异常")

    _check_thread = threading.Thread(target=loop, daemon=True, name="wechat-ip")
    _check_thread.start()


def stop():
    """停止定时检测。"""
    _stop.set()
    global _check_thread
    if _check_thread:
        _check_thread.join(timeout=5)
        _check_thread = None
