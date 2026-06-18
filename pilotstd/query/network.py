# pilotstd/query/network.py — 网络请求重试 + 异常监控（线程安全）
# 区分临时性错误（超时/连接重置/DNS/5xx → 重试1次）和永久性错误（4xx/解析失败 → 不重试）
# 限制最大重定向次数 5 次，防止恶意重定向链

import logging
import threading
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {502, 503, 504}  # 临时性服务端错误可重试
MAX_RETRIES = 1                     # 最多重试 1 次（避免过度消耗）
MAX_REDIRECTS = 5                   # 最大重定向次数，防恶意重定向链
DEFAULT_TIMEOUT = 15                # 默认请求超时秒数

# 通用 User-Agent（公告适配器等模块可复用）
CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"


class NetworkMonitor:
    """网络异常计数器（线程安全）。模块级单例保证全局唯一实例。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._errors: dict[str, int] = {}  # {site_name: count}
        self._retried: dict[str, int] = {}  # {site_name: count}

    def record_error(self, site_name: str):
        with self._lock:
            self._errors[site_name] = self._errors.get(site_name, 0) + 1

    def record_retry(self, site_name: str):
        with self._lock:
            self._retried[site_name] = self._retried.get(site_name, 0) + 1

    def reset(self):
        with self._lock:
            self._errors.clear()
            self._retried.clear()

    @property
    def total_errors(self) -> int:
        return sum(self._errors.values())

    @property
    def total_retries(self) -> int:
        return sum(self._retried.values())

    def summary(self) -> str:
        """生成网络异常汇总文本。"""
        with self._lock:
            if not self._errors:
                return ""
            parts = []
            for site, count in sorted(self._errors.items(), key=lambda x: -x[1]):
                r = self._retried.get(site, 0)
                parts.append(f"{site}: {count} 次异常(重试 {r} 次)")
            return " | ".join(parts)


# 模块级唯一单例：Python import 天然保证仅执行一次
_monitor = NetworkMonitor()


def get_monitor() -> NetworkMonitor:
    return _monitor


def safe_request(session: requests.Session, method: str, url: str,
                  site_name: str, timeout: int = DEFAULT_TIMEOUT,
                  **kwargs) -> Optional[requests.Response]:
    """统一的安全请求方法，带重试逻辑。

    临时性错误（超时、连接重置、5xx）重试 1 次；
    永久性错误（4xx）不重试。

    Args:
        session: requests.Session 实例
        method: HTTP 方法字符串（"GET" / "POST"）
        url: 请求 URL
        site_name: 站点标识（用于日志和监控）
        timeout: 超时秒数
        **kwargs: 传递给 session.request 的额外参数

    Returns:
        requests.Response 或 None（所有重试均失败）
    """
    # 限制最大重定向次数，防止恶意重定向链
    session.max_redirects = MAX_REDIRECTS

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                _monitor.record_retry(site_name)
                time.sleep(1)
                continue
            return resp
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < MAX_RETRIES:
                _monitor.record_retry(site_name)
                logger.debug("%s %s: %s — 重试中...", site_name, type(e).__name__, url)
                time.sleep(1)
            else:
                logger.warning("%s 请求异常(已重试): %s — %s", site_name, url, e)
        except requests.RequestException as e:
            logger.warning("%s 请求失败: %s — %s", site_name, url, e)
            _monitor.record_error(site_name)
            return None

    _monitor.record_error(site_name)
    return None


def safe_get(session: requests.Session, url: str, site_name: str,
             timeout: int = DEFAULT_TIMEOUT, **kwargs) -> Optional[requests.Response]:
    """带重试的 GET 请求。向后兼容封装。"""
    return safe_request(session, "GET", url, site_name, timeout, **kwargs)


def safe_post(session: requests.Session, url: str, site_name: str,
              timeout: int = DEFAULT_TIMEOUT, **kwargs) -> Optional[requests.Response]:
    """带重试的 POST 请求。向后兼容封装。"""
    return safe_request(session, "POST", url, site_name, timeout, **kwargs)


def safe_raw_get(url: str, site_name: str, timeout: int = DEFAULT_TIMEOUT,
                 **kwargs) -> Optional[requests.Response]:
    """不带 session 的简单 GET 请求（含重试）。供公告适配器等没有 session 的场景。"""
    return safe_request(requests, "GET", url, site_name, timeout, **kwargs)


def safe_raw_post(url: str, site_name: str, timeout: int = DEFAULT_TIMEOUT,
                  **kwargs) -> Optional[requests.Response]:
    """不带 session 的简单 POST 请求（含重试）。供 OCR 等场景。"""
    return safe_request(requests, "POST", url, site_name, timeout, **kwargs)
