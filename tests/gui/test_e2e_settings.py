# tests/gui/test_e2e_settings.py
"""E2E 测试 — SettingsHandler。

SettingsHandler 不在 MainWindowCore 中初始化。
它由 SettingsDialog / SettingsPage 独立创建（需要 QStackedWidget + QDialog 上下文），
build_all_pages() 需要完整的 Qt 控件树。

跳过独立 E2E 测试：SettingsHandler 的 23 个方法中 7 个是纯 Qt 页面构建，
8 个是控件事件回调，其余为 load/save 委托。此 Handler 的验证应由
test_settings_announce.py / test_settings_dialog.py 覆盖。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.skip(
    reason="SettingsHandler 不在 MainWindowCore 中，由 SettingsDialog 独立创建。"
    "build_all_pages 需要完整 QStackedWidget 控件树。"
    "已有 test_settings_announce.py / test_settings_dialog.py 覆盖。"
)
def test_settings_handler_requires_dialog(window, qtbot):
    pass
