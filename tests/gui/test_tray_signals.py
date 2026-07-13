"""验证系统托盘菜单的存在性与功能"""

from PyQt6.QtWidgets import QSystemTrayIcon

from pilotstd.i18n import _
from tests.gui.helpers import find_action_by_text, get_tray_menu


class TestTrayExistence:
    """托盘图标与菜单的基础检查。"""

    def test_tray_icon_exists(self, mock_main_window):
        """mock_main_window 应已创建系统托盘图标。"""
        assert hasattr(mock_main_window, "_tray")
        assert mock_main_window._tray is not None

    def test_tray_context_menu_exists(self, mock_main_window):
        """托盘应有右键菜单。"""
        menu = get_tray_menu(mock_main_window)
        assert menu is not None, "托盘右键菜单未初始化"

    def test_tray_show_action_exists(self, mock_main_window):
        """托盘菜单应包含「显示」选项。"""
        menu = get_tray_menu(mock_main_window)
        action = find_action_by_text(menu, "tray_show")
        assert action is not None, f"托盘菜单中未找到 'tray_show' (显示为 '{_('tray_show')}')"

    def test_tray_exit_action_exists(self, mock_main_window):
        """托盘菜单应包含「退出」选项。"""
        menu = get_tray_menu(mock_main_window)
        action = find_action_by_text(menu, "exit")
        assert action is not None, f"托盘菜单中未找到 'exit' (显示为 '{_('exit')}')"


class TestTrayBehavior:
    """托盘菜单功能验证。"""

    def test_tray_show_restores_window(self, mock_main_window, qtbot):
        """点击托盘「显示」应恢复窗口可见性。"""
        window = mock_main_window
        window.hide()
        assert not window.isVisible(), "窗口应先隐藏"

        menu = get_tray_menu(window)
        show_action = find_action_by_text(menu, "tray_show")
        show_action.trigger()

        qtbot.waitUntil(lambda: window.isVisible(), timeout=2000)
        assert window.isVisible()

    def test_tray_double_click_restores_window(self, mock_main_window, qtbot):
        """双击托盘图标应恢复窗口。"""
        window = mock_main_window
        window.hide()
        assert not window.isVisible()

        window._on_tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
        qtbot.waitUntil(lambda: window.isVisible(), timeout=2000)
        assert window.isVisible()
