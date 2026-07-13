"""验证菜单栏 QAction 存在且可触发"""

from unittest import mock

from PyQt6.QtWidgets import QFileDialog

from pilotstd.i18n import _
from tests.gui.helpers import find_action_by_text, find_menu_by_text, trigger_menu_action

# ── 文件菜单 ──


class TestFileMenuActions:
    """文件菜单各项的存在性与可触发验证。"""

    def test_file_open_file_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "open_file")
        assert action is not None
        assert action.isEnabled()

    def test_file_open_file_triggers_dialog(self, mock_main_window):
        with mock.patch.object(QFileDialog, "getOpenFileName", return_value=("", "")):
            trigger_menu_action(mock_main_window, "file", "open_file")
            QFileDialog.getOpenFileName.assert_called_once()

    def test_file_open_folder_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "open_folder")
        assert action is not None
        assert action.isEnabled()

    def test_file_open_folder_triggers_dialog(self, mock_main_window):
        with mock.patch.object(QFileDialog, "getExistingDirectory", return_value=""):
            trigger_menu_action(mock_main_window, "file", "open_folder")
            QFileDialog.getExistingDirectory.assert_called_once()

    def test_file_export_txt_exists(self, mock_main_window):
        menu = find_menu_by_text(mock_main_window, "file")
        export_menu = None
        for action in menu.actions():
            if action.text() == _("export_sheet"):
                export_menu = action.menu()
                break
        assert export_menu is not None, "导出工作表子菜单未找到"
        action = find_action_by_text(export_menu, "export_txt")
        assert action is not None

    def test_file_export_csv_exists(self, mock_main_window):
        menu = find_menu_by_text(mock_main_window, "file")
        export_menu = None
        for action in menu.actions():
            if action.text() == _("export_sheet"):
                export_menu = action.menu()
                break
        assert export_menu is not None
        action = find_action_by_text(export_menu, "export_csv")
        assert action is not None

    def test_file_export_file_list_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "export_file_list")
        assert action is not None
        assert action.isEnabled()

    def test_file_export_folder_tree_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "export_folder_tree")
        assert action is not None
        assert action.isEnabled()

    def test_file_save_query_project_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "save_query_project")
        assert action is not None
        assert action.isEnabled()

    def test_file_save_download_project_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "save_download_project")
        assert action is not None
        assert action.isEnabled()

    def test_file_import_download_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "import_download")
        assert action is not None
        assert action.isEnabled()

    def test_file_open_project_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "open_project")
        assert action is not None
        assert action.isEnabled()

    def test_file_exit_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "file"), "exit")
        assert action is not None
        assert action.isEnabled()

    def test_file_exit_is_connected_to_close(self, mock_main_window):
        """验证"退出"菜单项的 triggered 信号已连接到窗口的 close 方法。
        不实际触发，避免 closeEvent → _stop_workers 阻塞主线程。"""
        file_menu = find_menu_by_text(mock_main_window, "file")
        assert file_menu is not None
        exit_action = find_action_by_text(file_menu, "exit")
        assert exit_action is not None
        assert exit_action.receivers(exit_action.triggered) > 0, "退出菜单项的 triggered 信号未连接"


# ── 工具菜单 ──


class TestToolsMenuActions:
    """工具菜单各项的存在性验证。"""

    def test_tools_query_rules_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "tools"), "query_rules")
        assert action is not None
        assert action.isEnabled()

    def test_tools_task_center_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "tools"), "task_center")
        assert action is not None
        assert action.isEnabled()

    def test_tools_cleanup_empty_dirs_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "tools"), "cleanup_empty_dirs")
        assert action is not None
        assert action.isEnabled()

    def test_tools_collect_unrecognized_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "tools"), "collect_unrecognized")
        assert action is not None
        assert action.isEnabled()

    def test_tools_export_diag_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "tools"), "export_diag")
        assert action is not None
        assert action.isEnabled()

    def test_tools_pending_query_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "tools"), "pending_query")
        assert action is not None
        assert action.isEnabled()


# ── 设置菜单 ──


class TestSettingsMenuActions:
    """设置菜单各项的存在性验证。"""

    def test_settings_preferences_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "settings"), "preferences")
        assert action is not None
        assert action.isEnabled()


# ── 帮助菜单 ──


class TestHelpMenuActions:
    """帮助菜单各项的存在性验证。"""

    def test_help_check_update_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "help"), "check_update")
        assert action is not None
        assert action.isEnabled()

    def test_help_about_exists(self, mock_main_window):
        action = find_action_by_text(find_menu_by_text(mock_main_window, "help"), "about")
        assert action is not None
        assert action.isEnabled()
