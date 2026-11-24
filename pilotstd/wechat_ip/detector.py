# 模块：项目/_/_检测器脚本
"""多源公网 IP 检测——取众数确保准确性。"""

import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

# 并发拉取检测源的线程数上限（源数量本就很少，不必开太多）
_MAX_WORKERS = 4

IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

DEFAULT_SOURCES: list[tuple[str, Callable[[str], object]]] = [
    ("https://myip.ipip.net", lambda t: IP_PATTERN.search(t)),
    ("https://ddns.oray.com/checkip", lambda t: IP_PATTERN.search(t)),
    ("https://ip.3322.net", lambda t: IP_PATTERN.search(t) if IP_PATTERN.search(t) else None),
    ("https://4.ipw.cn", lambda t: t.strip() if t.strip() else None),
]

TIMEOUT = 8


def _validate_ip(ip: str) -> bool:
    """校验 IPv4 合法性。"""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def _fetch_one(url: str, extractor: Callable[[str], object]) -> Optional[str]:
    """从单个检测源取 IP；失败返回 None（异常不外抛，由调用方汇总）。"""
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "curl/8"})
        resp.encoding = "utf-8"
        result = extractor(resp.text)
        if not result:
            return None
        ip = result.group(0) if hasattr(result, "group") else str(result).strip()
        if _validate_ip(ip):
            logger.debug("IP检测源 %s → %s", url, ip)
            return ip
        return None
    except Exception as e:
        logger.warning("IP probe source failed: %s (%s)", url, e)
        return None


def detect_ip(sources: list[tuple[str, Callable[[str], object]]] | None = None) -> Optional[str]:
    """从多个检测源获取公网 IP，取众数返回。

    每个源返回的数据格式不同，通过提取函数统一抽取 IP 字符串。

    ── 为什么改为并发 + 总预算（NEW-25，2026-11-23）──
    原实现**串行**请求 4 个源，每个 `timeout=TIMEOUT`。最坏情况（全部超时）
    总耗时 = 4 × TIMEOUT，调用方（定时任务/启动流程）被拖住数倍于单源超时。

    改为线程池并发后：
      - 正常情况总耗时 ≈ 最慢的那个源（而不是 4 个之和）；
      - 用 `_TOTAL_BUDGET` 给整体设上限，超时的源按失败处理（不影响已拿到的结果）。
    """
    srcs = sources or DEFAULT_SOURCES
    if not srcs:
        logger.warning("IP probe source list is empty")
        return None

    ips: list[str] = []
    # 并发拉取；总预算略大于单源超时，避免正常的慢源被误杀
    budget = max(TIMEOUT * 2, TIMEOUT + 1)
    with ThreadPoolExecutor(max_workers=min(len(srcs), _MAX_WORKERS)) as pool:
        futures = {pool.submit(_fetch_one, url, extractor): idx for idx, (url, extractor) in enumerate(srcs)}
        results: dict[int, str] = {}
        try:
            for future in as_completed(futures, timeout=budget):
                ip = future.result()
                if ip:
                    results[futures[future]] = ip
        except FuturesTimeoutError:
            # 总预算耗尽：已完成的 `future` 结果已收集，未完成的按失败处理
            pending = [srcs[futures[f]][0] for f in futures if not f.done()]
            logger.warning(
                "IP probe budget %.1fs exhausted, %d/%d sources pending: %s",
                budget,
                len(pending),
                len(srcs),
                pending,
            )
    # ⚠️ 必须按**源顺序**回填，不能按完成顺序 ——
    # `Counter.most_common` 平票时按**插入顺序**决定胜者，并发完成顺序不确定，
    # 直接 `append` 会让 2v2 平票结果在多次运行间漂移（e2e 已锁该契约）。
    ips = [results[i] for i in sorted(results)]

    if not ips:
        logger.warning("所有 IP 检测源均失败")
        return None

    # 取众数
    counter = Counter(ips)
    most_common = counter.most_common(1)[0]
    ip, count = most_common
    if len(ips) >= 2 and count >= 2:
        logger.info("IP检测一致: %s (%d/%d 源一致)", ip, count, len(ips))
    elif len(ips) == 1:
        logger.info("IP检测结果: %s (仅 1 个源可用)", ip)
    else:
        logger.warning("IP检测不一致: %s 取众数=%s", dict(counter), ip)
    return ip
