# 模块：OCR 主备回退（云端/本地）
"""按配置优先尝试一个 provider，失败时用另一个，避免云端配额/本地缺页直接失败。"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

from ._base import BaseOcrProvider, OcrResult, OcrScheduler
from ._local import LocalOcrProvider

logger = logging.getLogger(__name__)


class FallbackOcrProvider(BaseOcrProvider):
    """整份 PDF 级别的主备回退；由 _ocr_pdf 识别 full_pdf 后一次调用。"""

    full_pdf = True

    def __init__(self, primary: BaseOcrProvider, fallback: BaseOcrProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def name(self) -> str:
        return f"{self._primary.name}+{self._fallback.name}"

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        """先跑主 provider，空文本时再跑备 provider。"""
        text = self._run(self._primary, pdf_bytes)
        if text.strip():
            return OcrResult(text=text)
        # 主 provider 空文本（无文本层/配额/网络失败）时才调用备 provider
        text = self._run(self._fallback, pdf_bytes)
        if not text.strip():
            return OcrResult(error="both OCR providers returned empty", error_type="ocr_empty")
        return OcrResult(text=text)

    def _run(self, provider: BaseOcrProvider, pdf_bytes: bytes) -> str:
        """按 provider 类型选择整份/逐页调用；异常返回空文本以触发备 provider。"""
        try:
            if isinstance(provider, OcrScheduler):
                return provider.recognize_pdf(pdf_bytes, page_num=1) or ""
            if isinstance(provider, LocalOcrProvider):
                return self._run_local(provider, pdf_bytes)
            # 直接云 provider（单 provider 旧模式）逐页调用
            return self._run_pages(provider, pdf_bytes)
        except Exception as exc:
            logger.warning("OCR provider %s failed: %s", provider.name, exc)
            return ""

    @staticmethod
    def _run_local(provider: LocalOcrProvider, pdf_bytes: bytes) -> str:
        """本地 provider 逐页识别，逐页释放图像内存。"""
        from ._pdf_utils import _pdf_page_count

        texts = []
        for page in range(1, _pdf_page_count(pdf_bytes) + 1):
            result = provider.recognize_pdf(pdf_bytes, page_num=page)
            if result.ok and result.text:
                texts.append(result.text)
        return "\n".join(texts)

    @staticmethod
    def _run_pages(provider: BaseOcrProvider, pdf_bytes: bytes) -> str:
        """直接云 provider 没有整本接口，拆单页调用。"""
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(BytesIO(pdf_bytes))
        texts = []
        for page in reader.pages:
            writer = PdfWriter()
            writer.add_page(page)
            buf = BytesIO()
            writer.write(buf)
            result: Any = provider.recognize_pdf(buf.getvalue(), page_num=1)
            text = getattr(result, "text", None) if not isinstance(result, str) else result
            if text:
                texts.append(text)
        return "\n".join(texts)
