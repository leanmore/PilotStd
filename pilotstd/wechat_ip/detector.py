# 模块：pilotstd/wechat_ip/ip_detector.py
"""多源公网 IP 检测——取众数确保准确性。"""

import logging
import re
from collections import Counter
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

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


def detect_ip(sources: list[tuple[str, Callable[[str], object]]] | None = None) -> Optional[str]:
    """从多个检测源获取公网 IP，取众数返回。

    每个源返回的数据格式不同，通过提取函数统一抽取 IP 字符串。
    """
    srcs = sources or DEFAULT_SOURCES
    ips: list[str] = []
    for url, extractor in srcs:
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "curl/8"})
            resp.encoding = "utf-8"
            result = extractor(resp.text)
            if result:
                ip = result.group(0) if hasattr(result, "group") else str(result).strip()
                if _validate_ip(ip):
                    ips.append(ip)
                    logger.debug("IP检测源 %s → %s", url, ip)
        except Exception as e:
            logger.debug("IP检测源 %s 失败: %s", url, e)

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
