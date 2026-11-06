"""统一时间工具：所有业务时间使用带时区感知的 ISO 8601。

容器/桌面都通过本模块取时间，禁止业务代码直接 datetime.now()。

时区来源：环境变量 `TZ`（如 Asia/Shanghai）；缺失时回退系统本地时区，
系统也无法确定时按 UTC 运行（容器基础镜像默认）。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

logger = logging.getLogger("pilotstd.time")

# 全局唯一 UTC 兜底；TZ 缺失且系统时区不可用时使用
_UTC = timezone.utc


def local_tz() -> timezone | ZoneInfo:
    """解析 TZ 环境变量；非法/缺失时回退系统本地时区，最终回退 UTC。"""
    # 优先使用显式 TZ（容器 compose 固定 Asia/Shanghai）
    name = os.environ.get("TZ", "").strip()
    zone: tzinfo | None = None
    if name:
        try:
            zone = ZoneInfo(name)
        except Exception as exc:
            logger.warning("TZ=%s 无法解析，回退系统时区: %s", name, exc)  # i18n-allow: 内部日志
    if zone is None:
        # 无 TZ 时按容器基础镜像的本地时区（通常 UTC）运行
        try:
            zone = datetime.now().astimezone().tzinfo
        except Exception as exc:
            logger.warning("系统时区探测失败，按 UTC 运行: %s", exc)  # i18n-allow: 内部日志
    if isinstance(zone, (timezone, ZoneInfo)):
        return zone
    return _UTC


def now() -> datetime:
    """当前时间（带时区）。"""
    return datetime.now(local_tz())


def iso_now() -> str:
    """当前时间 ISO 8601（秒级，带偏移量）。"""
    return now().isoformat(timespec="seconds")


def ensure_aware(dt: datetime) -> datetime:
    """无时区的 datetime 按本地时区补齐（历史裸时间按系统时区解释）。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=local_tz())
    return dt


def parse_iso(value: object) -> datetime | None:
    """解析历史/新格式时间字符串为带时区 datetime；失败返回 None。"""
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=local_tz())
        except ValueError:
            continue
    parsed = None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    return ensure_aware(parsed) if parsed is not None else None


def to_iso(value: object) -> str:
    """把历史时间字符串规范为 ISO 8601 带偏移量；无法解析时原样返回。"""
    dt = parse_iso(value)
    if dt is None:
        return "" if value is None else str(value)
    return dt.isoformat(timespec="seconds")


def days_ago_iso(days: int) -> str:
    """用于 retention：当前时间减 N 天的 ISO 字符串（带偏移量）。"""
    return (now() - timedelta(days=days)).isoformat(timespec="seconds")
