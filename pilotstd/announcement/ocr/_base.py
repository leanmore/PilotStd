# 模块：公告文字识别共享基类、数据模型、基础设施与工具函数
"""公告便携文档文字识别 —— 基类与调度基础设施。"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

# 便携文档工具函数（从页数检测和拆页模块重导出以兼容旧引用）
from ._pdf_utils import (  # noqa: F401
    _pdf_page_count,
    _set_thread_priority_idle,
    _split_pdf_pages,
)

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    """文字识别调用结果。成功则文本有效；失败则错误信息有效。"""

    text: str | None = None
    error: str | None = None
    error_code: str | None = None  # 原始错误码（编号如十八或请求频率超限等）
    error_type: str | None = None  # 错误类型：请求频率超限、月配额超限、日配额超限、超时或其他
    pdf_pages: int = 0  # 远端接口返回的总页数（交叉验证用）

    @property
    def ok(self) -> bool:
        return self.text is not None


class BaseOcrProvider(ABC):
    """文字识别提供商基类。用户可通过配置管理器配置切换。"""

    @abstractmethod
    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        """识别便携文档单页文本。返回识别结果。"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """提供商标识名，用于日志和配置。"""
        ...


# 分隔


class OcrCounters:
    """月度调用计数器，线程安全，每次加一后立即落盘。"""

    _LIMITS = {"baidu": 800, "tencent": 800, "aliyun": 150}

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        """从配置数据文件加载计数器。跨月自动清零，文件缺失时返回默认值。"""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"month": "", "baidu": 0, "tencent": 0, "aliyun": 0}
        current = datetime.now().strftime("%Y-%m")
        if data.get("month") != current:
            data = {"month": current, "baidu": 0, "tencent": 0, "aliyun": 0}
        return data  # type: ignore[no-any-return]  # 数据加载结果无精确类型

    def _save(self) -> None:
        """原子写入计数器到配置文件：先写临时文件再替换，防止写中断损坏数据。"""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        # 先写临时文件再原子替换，保证写入中断不会损坏正式文件
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)
        os.replace(tmp, self._path)

    def can_accept(self, provider: str, pages: int) -> bool:
        """检查指定服务商的剩余配额是否足够处理给定页数。"""
        with self._lock:
            return self._data[provider] + pages <= self._LIMITS[provider]  # type: ignore[no-any-return]  # 数据加载结果无精确类型

    def remaining(self, provider: str) -> int:
        """返回指定服务商的剩余调用次数。"""
        with self._lock:
            return max(0, self._LIMITS[provider] - self._data[provider])  # type: ignore[no-any-return]  # 数据加载结果无精确类型

    def increment(self, provider: str) -> None:
        """指定服务商计数器加一并立即落盘，保证进程中断不丢计数。"""
        with self._lock:
            self._data[provider] += 1
            self._save()

    def get(self, provider: str) -> int:
        """返回指定服务商当月的累计调用次数。"""
        with self._lock:
            return self._data[provider]  # type: ignore[no-any-return]  # 数据加载结果无精确类型

    @property
    def month(self) -> str:
        with self._lock:
            return self._data["month"]  # type: ignore[no-any-return]  # 数据加载结果无精确类型


# 分隔


class ProviderCooling:
    """服务商冷却状态管理，线程安全。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._until: dict[str, float] = {}

    def is_hot(self, name: str) -> bool:
        """检查服务商是否处于可用（未冷却）状态。"""
        with self._lock:
            return time.time() >= self._until.get(name, 0)

    def set(self, name: str, level: str) -> None:
        """将服务商设为冷却状态。请求频次级等于五分钟，日级等于次日零点，月级等于次月首日零点。"""
        now = datetime.now()
        if level == "qps":
            # 请求频次超限：冷却五分钟
            until = time.time() + 300
        elif level == "day":
            # 日配额超限：冷却到次日零点（零点为零时零分零秒）
            until = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp()
        elif level == "month":
            # 月配额超限：冷却到次月首日零点（零点为零时零分零秒）
            if now.month == 12:
                nxt = now.replace(year=now.year + 1, month=1, day=1)
            else:
                nxt = now.replace(month=now.month + 1, day=1)
            until = nxt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        else:
            until = 0
        with self._lock:
            self._until[name] = until
        logger.warning("[OCR] %s 进入冷却: 级别=%s 冷却至=%.0f", name, level, until)

    def remaining(self, name: str) -> float:
        """返回服务商冷却剩余秒数，零表示已解冻。"""
        with self._lock:
            return max(0, self._until.get(name, 0) - time.time())


# ── 便携文档拆页工具 ────────────────────────────────


# ── 单槽位 ────────────────────────────────────────


class OcrSlot:
    """单条文字识别槽位——绑定一个服务商，按请求频次限速逐页发送附件。"""

    _SIZE_LIMITS = {
        "baidu": 2.5 * 1024 * 1024,
        "tencent": 5 * 1024 * 1024,
        "aliyun": 8 * 1024 * 1024,
    }

    def __init__(
        self,
        name: str,
        provider: BaseOcrProvider,
        qps: int,
        counters: OcrCounters,
        cooling: ProviderCooling,
    ):
        self.name = name
        self.provider = provider
        self._counters = counters
        self._cooling = cooling
        self._interval = 1.0 / qps if qps > 0 else 0.1

    def is_available(self, total_pages: int) -> bool:
        """检查槽位是否可用：服务商非空、未冷却、配额充足。"""
        if self.provider is None:
            return False
        # 冷却中直接拒绝，避免无意义的请求浪费配额
        if not self._cooling.is_hot(self.name):
            return False
        # 检查月度配额是否够涵盖整个便携文档的页数
        if not self._counters.can_accept(self.name, total_pages):
            logger.warning(
                "[OCR] %s 计数超限: %d/%d 需%d页",
                self.name,
                self._counters.get(self.name),
                self._counters.remaining(self.name),
                total_pages,
            )
            return False
        return True

    def process(
        self,
        pages: list[bytes],
        label: str,
        emergency: "OcrSlot | None",
        stop_event: threading.Event,
    ) -> list[str]:
        """处理附件页列表。返回提取的文本列表。失败时回退到应急槽位。"""
        results = []
        total = len(pages)
        for i, page in enumerate(pages):
            if stop_event.is_set():
                logger.info("[OCR] %s 收到停止信号，已完成 %d/%d 页", self.name, i, total)
                break
            # 请求频次限速：每页之间等待间隔时间
            time.sleep(self._interval)
            result = self.provider.recognize_pdf(page, page_num=1)
            if result.ok:
                results.append(result.text)
                self._counters.increment(self.name)
                logger.info("[OCR] %s %s 第%d/%d页 成功", self.name, label, i + 1, total)
                # 首页返回的远端页数与本地拆页数交叉验证
                if i == 0 and result.pdf_pages > 0 and result.pdf_pages != total:
                    logger.warning(
                        "[OCR] %s 远端接口返回页数=%d 不等于本地=%d，以本地为准",
                        self.name,
                        result.pdf_pages,
                        total,
                    )
            else:
                err_type = result.error_type or "other"
                # 限流类错误触发冷却，避免短时间内继续冲击远端接口
                if err_type in ("qps", "month", "day"):
                    self._cooling.set(self.name, err_type)
                logger.warning(
                    "[OCR] %s %s 页%d/%d 错误(%s) 剩余%d页",
                    self.name,
                    label,
                    i + 1,
                    total,
                    result.error_code or err_type,
                    total - i - 1,
                )
                if emergency and (i + 1) < total:
                    remaining = pages[i + 1 :]
                    filtered = [r for r in results if r is not None]
                    return emergency._finish_remaining(remaining, label, stop_event, filtered)
                break
        logger.info("[OCR] %s %s 完成 (%d/%d页)", self.name, label, len(results), total)
        return [r for r in results if r is not None]

    def _finish_remaining(
        self,
        pages: list[bytes],
        label: str,
        stop_event: threading.Event,
        existing: list[str],
    ) -> list[str]:
        """应急接管剩余页。"""
        logger.warning(
            "[OCR] %s 应急接管 %s 页%d-%d",
            self.name,
            label,
            len(existing) + 1,
            len(existing) + len(pages),
        )
        for i, page in enumerate(pages):
            if stop_event.is_set():
                break
            time.sleep(self._interval)
            result = self.provider.recognize_pdf(page, page_num=1)
            if result.ok and result.text is not None:
                existing.append(result.text)
                self._counters.increment(self.name)
            else:
                logger.error("[OCR] %s 应急也失败: %s", self.name, result.error)
                break
        return existing

    def check_page_size(self, size: int) -> bool:
        return size <= self._SIZE_LIMITS.get(self.name, 10 * 1024 * 1024)


# ── 双槽调度器 ────────────────────────────────────


class OcrScheduler(BaseOcrProvider):
    """双槽并行文字识别调度器。"""

    def __init__(
        self,
        baidu_slot: OcrSlot | None,
        tencent_slot: OcrSlot | None,
        aliyun_slot: OcrSlot | None,
        stop_event: threading.Event,
        counters: OcrCounters,
        cooling: ProviderCooling,
    ):
        # 仅保留非空槽位，备选提供商作为应急备胎不在常规调度队列中
        self._slots = [s for s in (baidu_slot, tencent_slot) if s is not None]
        self._alibaba = aliyun_slot
        self._stop = stop_event
        self._counters = counters
        self._cooling = cooling
        self._active_lock = threading.Condition()
        self._active = 0
        _set_thread_priority_idle()

    @property
    def name(self) -> str:
        return "scheduler"

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> Optional[str]:  # type: ignore[override]
        """外部入口——入槽并阻塞等待完成。兼容文字识别基类接口。"""
        pages = _split_pdf_pages(pdf_bytes)
        total = len(pages)
        label = f"附件-{id(pdf_bytes):x}"

        # 等待空闲槽位：用条件变量实现生产者至消费者模式
        with self._active_lock:
            while self._active >= len(self._slots) and not self._stop.is_set():
                self._active_lock.wait(timeout=1)
            if self._stop.is_set():
                return None
            self._active += 1

        slot = self._pick_slot(total)
        if slot is None:
            with self._active_lock:
                self._active -= 1
                self._active_lock.notify_all()
            logger.error("[OCR] %s 无可用槽位", label)
            return None

        logger.info("[OCR] %s槽 接收 %s (%d页)", slot.name, label, total)
        try:
            results = slot.process(pages, label, emergency=self._alibaba, stop_event=self._stop)
            return "\n".join(results) if results else None
        finally:
            with self._active_lock:
                self._active -= 1
                self._active_lock.notify_all()

    def _pick_slot(self, total_pages: int) -> Optional[OcrSlot]:
        """选可用槽位——优先已用次数少的，实现简单负载均衡。"""
        available = [s for s in self._slots if s.is_available(total_pages)]
        if not available:
            return None
        available.sort(key=lambda s: self._counters.get(s.name))
        return available[0]
