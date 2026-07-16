# tests/gui/test_e2e_settings_io.py
"""E2E 测试 — SettingsConfigIO。

SettingsConfigIO 是 SettingsHandler 的内部组件（通过 self._io 访问），
不在 MainWindowCore 中。其 load/save 方法依赖 SettingsHandler 的控件引用
（如 _theme_combo / _lang_combo / _root_dir），需要完整 SettingsDialog 上下文。

跳过独立 E2E 测试：配置读写由 SettingsHandler 的测试间接覆盖。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.skip(
    reason="SettingsConfigIO 是 SettingsHandler 的内部组件（_io），"
    "不在 MainWindowCore 中。需要完整 SettingsDialog 控件树。"
)
def test_settings_io_requires_settings_handler(window, qtbot):
    pass
