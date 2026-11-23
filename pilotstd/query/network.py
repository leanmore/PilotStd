# 项目/查询/脚本—网络请求重试+异常监控（线程安全）
# 区分临时性错误（超时/连接重置//5→重试1次）和永久性错误（4/解析失败→不重试）
# 限制最大重定向次数 5 次，防止恶意重定向链

import logging
import threading
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {502, 503, 504}  # 临时性服务端错误可重试
MAX_RETRIES = 1  # 最多重试 1 次（避免过度消耗）
MAX_REDIRECTS = 5  # 最大重定向次数，防恶意重定向链
DEFAULT_TIMEOUT = 15  # 默认请求超时秒数

# 通用-（公告适配器等模块可复用）
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"  # noqa: E501
)


class NetworkMonitor:
    """网络异常计数器（线程安全）。模块级单例保证全局唯一实例。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._errors: dict[str, int] = {}  # {site_name: count}
        self._retried: dict[str, int] = {}  # {site_name: count}

    def record_error(self, site_name: str) -> None:
        """记录一次站点网络错误（线程安全）。"""
        with self._lock:
            self._errors[site_name] = self._errors.get(site_name, 0) + 1

    def record_retry(self, site_name: str) -> None:
        """记录一次站点重试（线程安全）。"""
        with self._lock:
            self._retried[site_name] = self._retried.get(site_name, 0) + 1

    def reset(self) -> None:
        """清空所有错误和重试计数器（线程安全）。"""
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


# 模块级唯一单例：程序天然保证仅执行一次
_monitor = NetworkMonitor()


def get_monitor() -> NetworkMonitor:
    return _monitor


def safe_request(
    session: requests.Session,
    method: str,
    url: str,
    site_name: str,
    timeout: int = DEFAULT_TIMEOUT,
    log_failures: bool = True,
    **kwargs: Any,
) -> Optional[requests.Response]:
    """统一的安全请求方法，带重试逻辑。

    临时性错误（超时、连接重置、5xx）重试 1 次；
    永久性错误（4xx）不重试。

    Args:
        session: requests.Session 实例
        method: HTTP 方法字符串（"GET" / "POST"）
        url: 请求 URL
        site_name: 站点标识（用于日志和监控）
        timeout: 超时秒数
        log_failures: 失败时是否打 WARNING。健康检查每小时探活一次，
            由调用方负责"仅状态变化时告警"，故探活传 False（失败降到 DEBUG），
            避免重复告警淹没有效信号；业务请求保持 True。
        **kwargs: 传递给 session.request 的额外参数

    Returns:
        requests.Response 或 None（所有重试均失败）
    """
    # 限制最大重定向次数，防止恶意重定向链
    session.max_redirects = MAX_REDIRECTS

    def _warn(msg: str, *args: Any) -> None:
        """按调用方要求选择失败日志级别。"""
        (logger.warning if log_failures else logger.debug)(msg, *args)

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                _monitor.record_retry(site_name)
                time.sleep(1)
                continue
            # 4xx/5xx（非可重试）记录警告，避免健康检查静默宕机
            if resp.status_code >= 400:
                _warn("%s HTTP %s: %s", site_name, resp.status_code, url)
            return resp
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < MAX_RETRIES:
                _monitor.record_retry(site_name)
                logger.debug("%s %s: %s — 重试中...", site_name, type(e).__name__, url)
                time.sleep(1)
            else:
                _warn("%s 请求异常(已重试): %s — %s", site_name, url, e)
        except requests.RequestException as e:
            _warn("%s 请求失败: %s — %s", site_name, url, e)
            _monitor.record_error(site_name)
            return None

    _monitor.record_error(site_name)
    return None


def safe_get(
    session: requests.Session,
    url: str,
    site_name: str,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> Optional[requests.Response]:
    """带重试的 GET 请求。向后兼容封装。"""
    return safe_request(session, "GET", url, site_name, timeout, **kwargs)


def safe_post(
    session: requests.Session,
    url: str,
    site_name: str,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> Optional[requests.Response]:
    """带重试的 POST 请求。向后兼容封装。"""
    return safe_request(session, "POST", url, site_name, timeout, **kwargs)


def safe_raw_get(
    url: str, site_name: str, timeout: int = DEFAULT_TIMEOUT, **kwargs: Any
) -> Optional[requests.Response]:
    """不带 session 的简单 GET 请求（含重试）。供公告适配器等没有 session 的场景。

    ── 为什么用 with 且先 `resp.content` 再关（NEW-38）──
    原实现 `session = requests.Session(); return safe_request(...)` —— **每次调用
    都新建一个 Session 且永不关闭**，公告附件下载 / OCR 路径高频调用会持续泄漏连接池。

    但这里不能简单 `with requests.Session() as s: return safe_request(...)`：
    调用方拿到 `resp` 后要读 `resp.content`，而 Session 关闭会让**未读取的响应体**
    无法再流式读取（`requests` 的 `Response.content` 是惰性读取的）。
    故：先在 `with` 块内把响应体读完（`resp.content` 触发读取并缓存到内存），
    再让 `with` 关闭 Session —— 之后调用方读 `resp.content` 命中的是内存缓存，
    行为与原实现完全一致。
    """
    with requests.Session() as session:
        resp = safe_request(session, "GET", url, site_name, timeout, **kwargs)
        if resp is not None:
            # 触发并缓存响应体（读失败不应影响返回：原实现同样可能在读取时抛错）
            try:
                _ = resp.content
            except Exception as e:
                logger.warning("%s 响应体读取失败: %s — %s", site_name, url, e)  # i18n-allow: 内部运维日志
        return resp


def safe_raw_post(
    url: str, site_name: str, timeout: int = DEFAULT_TIMEOUT, **kwargs: Any
) -> Optional[requests.Response]:
    """不带 session 的简单 POST 请求（含重试）。供 OCR 等场景。

    同 `safe_raw_get`：`with` 内先读响应体再关闭 Session（NEW-38）。
    """
    with requests.Session() as session:
        resp = safe_request(session, "POST", url, site_name, timeout, **kwargs)
        if resp is not None:
            try:
                _ = resp.content
            except Exception as e:
                logger.warning("%s 响应体读取失败: %s — %s", site_name, url, e)  # i18n-allow: 内部运维日志
        return resp
