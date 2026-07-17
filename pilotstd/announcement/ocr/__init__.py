# pilotstd/announcement/ocr/__init__.py
# OCR 提供商抽象层 — 工厂函数与公开 API
"""公告 PDF OCR 识别。默认百度云 basicGeneralPdf 接口，用户可配腾讯云/阿里云。

各平台均直接接收 PDF 文件（base64 编码后 ≤4~10MB），无需 PDF→图片转换。
百度云通用文字识别标准版每月免费 1000 次，月均用量 ~50 次，不花钱。
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

from ._aliyun import AliyunOcrProvider
from ._baidu import BaiduOcrProvider
from ._base import (
    BaseOcrProvider,
    OcrCounters,
    OcrResult,
    OcrScheduler,
    OcrSlot,
    ProviderCooling,
    _pdf_page_count,
    _set_thread_priority_idle,
    _split_pdf_pages,
)
from ._tencent import TencentOcrProvider

logger = logging.getLogger(__name__)


# ── 工厂函数 ───────────────────────────────────────────────────────


def create_ocr_provider(config: dict[str, Any], data_dir: str = "") -> Optional[BaseOcrProvider]:
    """创建 OCR 调度器（多 provider 共存）或单个 provider（旧模式兼容）。

    新键（推荐）：
      baidu_api_key / baidu_secret_key
      tencent_secret_id / tencent_secret_key
      aliyun_access_key_id / aliyun_access_key_secret
    旧键（兼容，单 provider 模式）：
      api_key / secret_key / secret_id / access_key_id / access_key_secret
    """
    # 旧模式兼容：显式指定 provider 时走单 provider 路径
    explicit = config.get("provider", "")
    if explicit in ("baidu", "tencent", "aliyun"):
        if explicit == "baidu":
            return _create_baidu(config)
        elif explicit == "tencent":
            return _create_tencent(config)
        else:
            return _create_aliyun(config)

    # 新模式：创建全部有凭据的 provider，返回调度器
    if not data_dir:
        from ...core.config import get_data_dir

        data_dir = get_data_dir()
    counter_path = os.path.join(data_dir, "ocr_counters.json")
    counters = OcrCounters(counter_path)
    cooling = ProviderCooling()

    baidu = _create_baidu(config)
    tencent = _create_tencent(config)
    aliyun = _create_aliyun(config)

    stop = threading.Event()
    baidu_slot = OcrSlot("baidu", baidu, 2, counters, cooling) if baidu else None
    tencent_slot = OcrSlot("tencent", tencent, 10, counters, cooling) if tencent else None
    aliyun_slot = OcrSlot("aliyun", aliyun, 10, counters, cooling) if aliyun else None

    if not baidu_slot and not tencent_slot:
        if aliyun_slot:
            logger.warning("仅阿里云可用，百度云和腾讯云均未配置")
            return aliyun_slot  # type: ignore[return-value]
        logger.warning("无可用OCR提供商")
        return None
    return OcrScheduler(baidu_slot, tencent_slot, aliyun_slot, stop, counters, cooling)


def _create_baidu(config: dict[str, Any]) -> Optional["BaiduOcrProvider"]:
    """根据配置创建百度云 OCR 提供商实例，未配置则返回 None。"""
    api_key = config.get("baidu_api_key", "") or config.get("api_key", "")
    secret_key = config.get("baidu_secret_key", "") or config.get("secret_key", "")
    if not api_key or not secret_key:
        logger.warning("百度云 OCR 未配置 api_key/secret_key，跳过")
        return None
    return BaiduOcrProvider(api_key=api_key, secret_key=secret_key)


def _create_tencent(config: dict[str, Any]) -> Optional["TencentOcrProvider"]:
    """根据配置创建腾讯云 OCR 提供商实例，未配置则返回 None。"""
    secret_id = config.get("tencent_secret_id", "") or config.get("secret_id", "")
    secret_key = config.get("tencent_secret_key", "") or config.get("secret_key", "")
    if not secret_id or not secret_key:
        logger.warning("腾讯云 OCR 未配置 secret_id/secret_key，跳过")
        return None
    return TencentOcrProvider(secret_id=secret_id, secret_key=secret_key)


def _create_aliyun(config: dict[str, Any]) -> Optional["AliyunOcrProvider"]:
    """根据配置创建阿里云 OCR 提供商实例，未配置则返回 None。"""
    ak_id = config.get("aliyun_access_key_id", "") or config.get("access_key_id", "")
    ak_secret = config.get("aliyun_access_key_secret", "") or config.get("access_key_secret", "")
    if not ak_id or not ak_secret:
        logger.warning("阿里云 OCR 未配置 access_key_id/access_key_secret，跳过")
        return None
    return AliyunOcrProvider(access_key_id=ak_id, access_key_secret=ak_secret)


__all__ = [
    "AliyunOcrProvider",
    "BaseOcrProvider",
    "BaiduOcrProvider",
    "OcrCounters",
    "OcrResult",
    "OcrSlot",
    "OcrScheduler",
    "ProviderCooling",
    "TencentOcrProvider",
    "_pdf_page_count",
    "_set_thread_priority_idle",
    "_split_pdf_pages",
    "create_ocr_provider",
]
