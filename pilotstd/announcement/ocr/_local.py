# 模块：本地 OCR provider（CPU，RapidOCR/ONNX）
"""可选本地 OCR：扫描版 PDF 在没有文本层时使用，避免依赖云端密钥/配额。"""

from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import shutil
import sys
import threading
from pathlib import Path

from ._base import BaseOcrProvider, OcrResult

logger = logging.getLogger(__name__)


def _default_model_dir() -> Path:
    """模型目录：环境变量 > 便携版 exe 同目录 > Docker 数据卷 > 项目根。"""
    env = os.environ.get("PILOTSTD_MODEL_DIR", "")
    if env:
        return Path(env)
    exe_name = Path(sys.executable).name.lower()
    # PyInstaller 用 sys.frozen；其他单文件打包器不一定设置，非 python 可执行文件同样视为便携版
    if getattr(sys, "frozen", False) or not exe_name.startswith("python"):
        return Path(sys.executable).resolve().parent / "models" / "ocr"
    if Path("/app/data").exists():
        return Path("/app/data/models/ocr")
    return Path(__file__).resolve().parents[3] / "models" / "ocr"


class LocalOcrProvider(BaseOcrProvider):
    """RapidOCR + onnxruntime CPU，单任务串行，限制页渲染尺寸。"""

    def __init__(
        self,
        scale: float = 150 / 72,
        max_side: int = 2000,
        model_dir: str | Path | None = None,
    ) -> None:
        self._scale = scale
        self._max_side = max_side
        self._model_dir = Path(model_dir) if model_dir else _default_model_dir()
        self._engine = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "local"

    def install_models(self) -> Path:
        """把 RapidOCR wheel 内置模型复制到应用模型目录，便于统一管理/升级。"""
        import rapidocr_onnxruntime

        source = Path(rapidocr_onnxruntime.__file__).resolve().parent / "models"
        version = importlib.metadata.version("rapidocr-onnxruntime")
        target = self._model_dir / "rapidocr" / version
        files = ("ch_PP-OCRv3_det_infer.onnx", "ch_PP-OCRv3_rec_infer.onnx", "ch_ppocr_mobile_v2.0_cls_infer.onnx")
        try:
            # 已安装且大小一致时直接复用，避免每次启动重复拷贝 13MB 模型
            if all(
                (target / name).exists() and (target / name).stat().st_size == (source / name).stat().st_size
                for name in files
            ):
                return target
            target.mkdir(parents=True, exist_ok=True)
            for name in files:
                # 先写临时文件再原子替换，下载/拷贝中断不破坏旧模型
                tmp = target / f".{name}.tmp"
                shutil.copy2(source / name, tmp)
                os.replace(tmp, target / name)
            (target / "manifest.json").write_text(
                json.dumps({"name": "rapidocr", "version": version, "files": files}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return target
        except OSError as exc:
            logger.warning("local OCR model install failed, use packaged models: %s", exc)
            return source

    def _get_engine(self):
        if self._engine is None:
            # onnxruntime/BLAS 在 import 前读取线程数；默认限制为 1，避免抢占宿主机
            os.environ.setdefault("OMP_NUM_THREADS", "1")
            os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
            os.environ.setdefault("MKL_NUM_THREADS", "1")
            from rapidocr_onnxruntime import RapidOCR

            models = self.install_models()
            self._engine = RapidOCR(
                det_model_path=str(models / "ch_PP-OCRv3_det_infer.onnx"),
                rec_model_path=str(models / "ch_PP-OCRv3_rec_infer.onnx"),
                cls_model_path=str(models / "ch_ppocr_mobile_v2.0_cls_infer.onnx"),
            )
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
                # 同一进程内串行识别，防止多个公告同时 OCR 抢满 CPU
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
