# 模块：本地 OCR provider（CPU，RapidOCR/ONNX）
"""可选本地 OCR：扫描版 PDF 在没有文本层时使用，避免依赖云端密钥/配额。"""

from __future__ import annotations

import logging
import os
import threading

from ._base import BaseOcrProvider, OcrResult

logger = logging.getLogger(__name__)


class LocalOcrProvider(BaseOcrProvider):
    """RapidOCR + onnxruntime CPU，单任务串行，限制页渲染尺寸。"""

    def __init__(self, scale: float = 150 / 72, max_side: int = 2000) -> None:
        self._scale = scale
        self._max_side = max_side
        self._engine = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "local"

    def _get_engine(self):
        if self._engine is None:
            # onnxruntime/BLAS 在 import 前读取线程数；默认限制为 1，避免抢占宿主机
            os.environ.setdefault("OMP_NUM_THREADS", "1")
            os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
            os.environ.setdefault("MKL_NUM_THREADS", "1")
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        """渲染指定页并用本地 RapidOCR 识别，返回单页文本。"""
        try:
            from io import BytesIO

            import numpy as np
            import pypdfium2 as pdfium
        except ImportError as exc:
            return OcrResult(error=f"local OCR dependencies missing: {exc}", error_type="missing_dependency")

        try:
            with self._lock:
                doc = pdfium.PdfDocument(BytesIO(pdf_bytes))
                try:
                    total = len(doc)
                    index = max(0, min(page_num - 1, total - 1))
                    page = doc[index]
                    bitmap = page.render(scale=self._scale)
                    image = bitmap.to_pil().convert("RGB")
                    if max(image.size) > self._max_side:
                        image.thumbnail((self._max_side, self._max_side))
                    result, _ = self._get_engine()(np.array(image))
                    text = "\n".join(row[1] for row in (result or []))
                    return OcrResult(text=text or None, pdf_pages=total)
                finally:
                    doc.close()
        except Exception as exc:
            logger.warning("local OCR failed: page=%s error=%s", page_num, exc)
            return OcrResult(error=str(exc), error_type="local_error")
