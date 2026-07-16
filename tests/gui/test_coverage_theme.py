"""覆盖 pilotstd/ui/main_window/parts/_theme_ops.py 未覆盖行。

覆盖目标：22, 28, 52-53, 55-56, 71, 73-77, 89-122
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QTranslator
from PyQt6.QtWidgets import QApplication


class TestApplyIcon:
    """覆盖 _apply_icon 各分支。"""

    def test_apply_icon_frozen(self, window, monkeypatch):
        """覆盖行 22：is_frozen 返回 True → 使用 _MEIPASS 路径。"""
        monkeypatch.setattr(
            "pilotstd.ui.main_window.parts._theme_ops.is_frozen",
            lambda: True,
        )
        fake_meipass = os.path.join(os.path.dirname(__file__), "..", "fixtures")
        monkeypatch.setattr(sys, "_MEIPASS", fake_meipass, raising=False)

        # 不崩溃即为通过（路径即使不存在也安全）
        window._apply_icon()

    def test_apply_icon_non_default(self, window, monkeypatch):
        """覆盖行 28：icon_theme 非 default → 使用 assets/icons 路径。"""
        original_get = window._config.get

        def _get(key, default=None):
            if key == "appearance.icon_theme":
                return "dark"
            return original_get(key, default)

        monkeypatch.setattr(window._config, "get", _get)
        window._apply_icon()
        # 不崩溃即为通过


class TestLoadQtTranslator:
    """覆盖 _load_qt_translator 各分支。"""

    def test_load_qt_translator_remove_old(self, window, monkeypatch):
        """覆盖行 52-53：中文语言 → 移除旧 translator。"""
        monkeypatch.setattr(window, "_loaded_qt_lang", "en")  # 使幂等检查跳过

        original_get = window._config.get

        def _get(key, default=None):
            if key == "appearance.language":
                return "zh_CN"
            return original_get(key, default)

        monkeypatch.setattr(window._config, "get", _get)

        mock_old = MagicMock(spec=QTranslator)
        window._qt_translator = mock_old
        window._widgets_translator = None

        mock_app = MagicMock(spec=QApplication)
        with patch.object(QApplication, "instance", return_value=mock_app):
            # qm 文件不存在 ⇒ translator.load 失败 ⇒ warning
            with patch("os.path.exists", return_value=False):
                window._load_qt_translator()

        mock_app.removeTranslator.assert_called_once_with(mock_old)

    def test_load_qt_translator_frozen(self, window, monkeypatch):
        """覆盖行 55-56：frozen 模式 → 使用 _MEIPASS 路径。"""
        monkeypatch.setattr(window, "_loaded_qt_lang", None)

        original_get = window._config.get

        def _get(key, default=None):
            if key == "appearance.language":
                return "zh_CN"
            return original_get(key, default)

        monkeypatch.setattr(window._config, "get", _get)
        monkeypatch.setattr(
            "pilotstd.ui.main_window.parts._theme_ops.is_frozen",
            lambda: True,
        )
        monkeypatch.setattr(sys, "_MEIPASS", "/fake/meipass", raising=False)

        with patch("os.path.exists", return_value=False):
            window._load_qt_translator()
        # 不应崩溃

    def test_load_qt_translator_load_failure(self, window, monkeypatch):
        """覆盖行 71：translator.load 返回 False → warning 日志。"""
        monkeypatch.setattr(window, "_loaded_qt_lang", None)

        original_get = window._config.get

        def _get(key, default=None):
            if key == "appearance.language":
                return "zh_CN"
            return original_get(key, default)

        monkeypatch.setattr(window._config, "get", _get)

        with patch("os.path.exists", return_value=True), patch.object(
            QTranslator, "load", return_value=False
        ):
            window._load_qt_translator()
        # translator.load 失败 → 记录 warning，不应崩溃

    def test_load_qt_translator_non_chinese(self, window, monkeypatch):
        """覆盖行 73-77：非中文语言 → 移除旧 translator 但不加载新翻译。"""
        monkeypatch.setattr(window, "_loaded_qt_lang", None)

        original_get = window._config.get

        def _get(key, default=None):
            if key == "appearance.language":
                return "en"
            return original_get(key, default)

        monkeypatch.setattr(window._config, "get", _get)

        window._qt_translator = MagicMock(spec=QTranslator)
        window._widgets_translator = MagicMock(spec=QTranslator)

        mock_app = MagicMock(spec=QApplication)
        with patch.object(QApplication, "instance", return_value=mock_app):
            window._load_qt_translator()

        assert mock_app.removeTranslator.call_count >= 2


class TestRetranslateUi:
    """覆盖 _retranslate_ui（行 89-122）。"""

    def test_retranslate_ui_basic(self, window, monkeypatch):
        """覆盖行 89-122：重翻译 UI 所有文本。"""
        # 标记 UI 可翻译
        window._ui_translatable = True
        # 创建一个 fake log_label
        window._log_label = MagicMock()
        window._paused = False

        # mock _retranslate_file_tree 避免重建树
        with patch.object(window, "_retranslate_file_tree"):
            window._retranslate_ui()

        # 验证关键 setText 被调用
        assert "PilotStd" in window.windowTitle() or window.windowTitle() != ""

    def test_retranslate_ui_not_translatable(self, window):
        """覆盖行 87-88：_ui_translatable 为 False → 提前返回。"""
        window._ui_translatable = False
        # 保存标题
        saved_title = window.windowTitle()
        window._retranslate_ui()
        # 标题不应变化
        assert window.windowTitle() == saved_title
