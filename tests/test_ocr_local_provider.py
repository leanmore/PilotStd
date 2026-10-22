"""本地 CPU OCR provider：工厂与依赖可用性测试（实际 PDF 识别由人工/集成样本覆盖）。"""

from __future__ import annotations

import pytest

from pilotstd.announcement.ocr import create_ocr_provider


def test_create_local_provider_when_dependencies_available() -> None:
    pytest.importorskip("rapidocr_onnxruntime")
    pytest.importorskip("pypdfium2")
    provider = create_ocr_provider({"provider": "local"})
    assert provider is not None
    assert provider.name == "local"


def test_local_provider_missing_dependencies_returns_none(monkeypatch) -> None:
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None if name.startswith("rapidocr") else object())
    assert create_ocr_provider({"provider": "local"}) is None
