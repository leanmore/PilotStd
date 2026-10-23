"""Windows OCR 设置页：识别方式 + 本地模型下载入口。"""

from unittest.mock import MagicMock


def test_ocr_page_has_provider_and_model_download(qtbot) -> None:
    from pilotstd.ui.core.handlers._settings import SettingsHandler

    handler = SettingsHandler(MagicMock())
    handler._build_ocr_page()
    assert handler._ocr_provider_combo is not None
    assert handler._ocr_provider_combo.count() == 2
    assert handler._ocr_download_btn is not None
    assert handler._ocr_model_status is not None
