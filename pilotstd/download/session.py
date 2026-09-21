# 模块：项目/下载/脚本
# 网络会话管理：轮换、重试退避、代理、随机延迟

import logging
import os
import random
import time
from typing import Any, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]


class _DefaultTimeoutSession(requests.Session):
    """带默认超时的 Session。

    为什么用子类而不是给实例打猴子补丁：`requests.Session.request` 的默认超时是"不超时"，
    若把 `s.request` 替换成 lambda 再用 `super(requests.Session, s)` 委派，super() 会从
    `requests.Session` **之后**开始查找，落在 `object` 上 → 任何请求都抛
    `AttributeError: 'super' object has no attribute 'request'`（2026-09-20 生产日志 427 条，
    收藏下载 0 成功）。子类覆盖 request 后由 `super()` 沿 MRO 正确定位到基类实现。
    """

    def __init__(self, default_timeout: float) -> None:
        super().__init__()
        self._default_timeout = default_timeout

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """未显式指定 timeout 时注入默认值（显式值优先）。"""
        kwargs.setdefault("timeout", self._default_timeout)
        return super().request(method, url, **kwargs)


class SessionManager:
    """管理 HTTP 会话，提供 UA 轮换、重试、代理、延迟等功能。"""

    def __init__(
        self,
        user_agents: Optional[List[str]] = None,
        proxy: Optional[str] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        default_timeout: int = 30,
    ) -> None:
        self._user_agents = user_agents or DEFAULT_USER_AGENTS
        # 未指定代理时自动检测系统代理（环境变量 > 系统设置）
        if not proxy:
            proxy = self._detect_system_proxy()
        self._proxy = proxy
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._default_timeout = default_timeout  # 从配置读取的默认超时秒数
        self._ua_index = 0
        self._last_request_time = 0.0

    def create_session(self) -> requests.Session:
        """创建带重试策略和默认超时的新会话。"""
        s = _DefaultTimeoutSession(self._default_timeout)
        s.headers.update({"User-Agent": self._next_ua()})

        if self._proxy:
            s.proxies = {"http": self._proxy, "https": self._proxy}

        retry_strategy = Retry(
            total=self._max_retries,
            backoff_factor=self._backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s

    def delay(self) -> None:
        """随机延迟，避免触发反爬。"""
        elapsed = time.time() - self._last_request_time
        wait = random.uniform(self._min_delay, self._max_delay)
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_request_time = time.time()

    def rotate_ua(self) -> None:
        """切换到下一个 UA。"""
        self._ua_index = (self._ua_index + 1) % len(self._user_agents)
        logger.debug(f"UA 已切换: #{self._ua_index}")

    def get_current_ua(self) -> str:
        return self._user_agents[self._ua_index % len(self._user_agents)]

    # ---- 内部 ----

    @staticmethod
    def _detect_system_proxy() -> str:
        """检测系统代理：环境变量 > Windows 系统设置。"""
        import urllib.request

        for var in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
            val = os.environ.get(var)
            if val:
                return val
        proxies = urllib.request.getproxies()
        return proxies.get("https") or proxies.get("http") or ""

    def _next_ua(self) -> str:
        ua = self._user_agents[self._ua_index % len(self._user_agents)]
        self._ua_index += 1
        return ua
