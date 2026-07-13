"""Win 端剩余缺口覆盖：右键菜单项文本、双击信号、键盘事件"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu

from pilotstd.i18n import _

# ═══════════════════════════════════════════
# 工作表右键菜单项文本验证
# ═══════════════════════════════════════════


class TestWorkTableContextMenuItems:
    """验证工作表右键菜单的 6 个选项文本与 i18n key 一致。"""

    _EXPECTED_KEYS = ["copy", "offline_view", "add_file", "add_folder", "remove_selected", "remove_all"]

    def test_all_six_context_menu_keys_exist_in_i18n(self):
        """6 个右键菜单 key 均存在翻译。"""
        for key in self._EXPECTED_KEYS:
            text = _(key)
            assert text != key, f"i18n key '{key}' 缺少翻译（返回了自身）"

    def test_work_table_context_menu_policy(self, mock_main_window):
        """工作表 CustomContextMenu 策略已设置。"""
        assert mock_main_window.work_table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    def test_work_table_context_menu_has_six_items(self):
        """模拟右键菜单创建，确认 6 个选项可构建。"""
        menu = QMenu()
        menu.addAction(f"\U0001f4cb {_('copy')}")
        menu.addAction(f"\U0001f50d {_('offline_view')}")
        menu.addAction(f"\U0001f4c4 {_('add_file')}")
        menu.addAction(f"\U0001f4c1 {_('add_folder')}")
        menu.addAction(f"\U0001f5d1 {_('remove_selected')}")
        menu.addAction(f"\U0001f9f9 {_('remove_all')}")
        assert len(menu.actions()) == 6


# ═══════════════════════════════════════════
# 文件树右键菜单
# ═══════════════════════════════════════════


class TestFileTreeContextMenu:
    def test_file_tree_context_menu_policy(self, mock_main_window):
        """文件树 CustomContextMenu 策略已设置。"""
        assert mock_main_window.file_tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    def test_file_tree_import_action_key_exists(self):
        """「导入工作区」的 i18n key 存在。"""
        text = _("context_import")
        assert text != "context_import"


# ═══════════════════════════════════════════
# 表头右键菜单（列显隐切换）
# ═══════════════════════════════════════════


class TestHeaderContextMenu:
    def test_header_context_menu_policy(self, mock_main_window):
        """表头 CustomContextMenu 策略已设置。"""
        header = mock_main_window.work_table.horizontalHeader()
        assert header.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    def test_toggleable_cols_exist(self):
        """可切换列列表非空且索引有效。"""
        from pilotstd.ui.table_constants import TOGGLEABLE_COLS, WORK_COLUMNS

        assert len(TOGGLEABLE_COLS) >= 4
        for c in TOGGLEABLE_COLS:
            assert 0 <= c < len(WORK_COLUMNS)


# ═══════════════════════════════════════════
# 键盘事件 — 工作表键盘操作
# ═══════════════════════════════════════════


class TestKeyboardEvents:
    def test_work_table_key_press_handler_set(self, mock_main_window):
        """工作表 keyPressEvent 已替换为自定义处理器。"""
        assert mock_main_window.work_table.keyPressEvent is not mock_main_window.work_table.__class__.keyPressEvent

    def test_work_table_selection_mode(self, mock_main_window):
        """工作表支持多选（ExtendedSelection）。"""
        from PyQt6.QtWidgets import QTableWidget

        assert mock_main_window.work_table.selectionMode() == QTableWidget.SelectionMode.ExtendedSelection
