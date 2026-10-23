# 模块：本地 OCR 模型下载与安装
"""从 RapidOCR 官方 wheel 下载模型并安装到应用 models/ocr 目录。

Windows 设置页通过本模块的 download_and_install 实现“开关直接下载”，
不要求用户手工解压或复制 ONNX 文件。
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from ._local import _default_model_dir

logger = logging.getLogger(__name__)

MODEL_VERSION = "1.2.3"
WHEEL_URL = (
    "https://files.pythonhosted.org/packages/b7/ef/"
    "0df9a58310895ab357f85df67935af6a8fb98f0965c7476cee6fcb966a7e/"
    "rapidocr_onnxruntime-1.2.3-py3-none-any.whl"
)
WHEEL_SHA256 = "c707d3a6eb72d13119afe9602d3cc36d8b2a4a4d74e9575cf1b0e67ed6a27819"
MODEL_FILES = (
    "ch_PP-OCRv3_det_infer.onnx",
    "ch_PP-OCRv3_rec_infer.onnx",
    "ch_ppocr_mobile_v2.0_cls_infer.onnx",
)


def target_dir(model_dir: Path | str | None = None) -> Path:
    """模型安装目标：<models/ocr>/rapidocr/<版本>。"""
    root = Path(model_dir) if model_dir else _default_model_dir()
    return root / "rapidocr" / MODEL_VERSION


def is_installed(model_dir: Path | str | None = None) -> bool:
    """三个模型文件都在目标目录时视为已安装。"""
    target = target_dir(model_dir)
    return all((target / name).exists() for name in MODEL_FILES)


def _extract_from_wheel(wheel: Path, target: Path) -> None:
    """只从 wheel 中解出三个 ONNX，避免把整个包散落到模型目录。"""
    prefix = "rapidocr_onnxruntime/models/"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel) as zf:
        names = [n for n in zf.namelist() if n.startswith(prefix) and Path(n).name in MODEL_FILES]
        if len(names) != len(MODEL_FILES):
            raise ValueError("wheel 中缺少 OCR 模型文件")  # i18n-allow
        # 每个文件先写临时文件再原子替换，下载中断不破坏旧模型
        for name in names:
            temp = target / f".{Path(name).name}.tmp"
            with zf.open(name) as src, temp.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            os.replace(temp, target / Path(name).name)


def install_wheel_bytes(data: bytes, model_dir: Path | str | None = None) -> Path:
    """安装已下载的 wheel 字节（供下载流程和测试复用）。"""
    target = target_dir(model_dir)
    with tempfile.TemporaryDirectory() as tmp:
        wheel = Path(tmp) / "rapidocr.whl"
        wheel.write_bytes(data)
        _extract_from_wheel(wheel, target)
    return target


def download_and_install(
    model_dir: Path | str | None = None,
    progress: Callable[[str], None] | None = None,
    url: str = WHEEL_URL,
    sha256: str = WHEEL_SHA256,
) -> Path:
    """下载 wheel、校验 SHA256、解出模型；返回安装目录。"""
    target = target_dir(model_dir)
    # 已安装直接复用，重复点下载不会重复拉 12MB
    if is_installed(model_dir):
        return target
    if progress:
        progress("正在下载本地 OCR 模型…")  # i18n-allow
    request = urllib.request.Request(url, headers={"User-Agent": "PilotStd"})
    with urllib.request.urlopen(request, timeout=120) as resp:  # noqa: S310 — 固定 HTTPS 官方源
        data = resp.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest.lower() != sha256.lower():
        raise ValueError("OCR 模型包 SHA256 校验失败")  # i18n-allow
    if progress:
        progress("正在解压模型…")  # i18n-allow
    with tempfile.TemporaryDirectory() as tmp:
        wheel = Path(tmp) / "rapidocr.whl"
        wheel.write_bytes(data)
        _extract_from_wheel(wheel, target)
    if progress:
        progress("本地 OCR 模型安装完成")  # i18n-allow
    return target
