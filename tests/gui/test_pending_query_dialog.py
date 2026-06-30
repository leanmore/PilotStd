# tests/gui/test_pending_query_dialog.py
# 测试 PendingQueryDialog — 对话框创建、本地数据库检测、清理逻辑

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_manager() -> MagicMock:
    """创建 mock StandardManager。"""
    mgr = MagicMock()
    mgr.get_query_sites.return_value = ["site_a", "site_b"]
    mgr.get_site_adapter.return_value = MagicMock(site_label="测试站点A")
    mgr.get_site_cooldown.return_value = 0
    mgr.is_requery_exhausted.return_value = False
    mgr.get_requery_count.return_value = 0
    mgr.query_local_cache.return_value = []
    mgr.query_engine.get_adapter.return_value = MagicMock()
    return mgr


@pytest.fixture
def mock_parsed_list() -> list:
    """创建 mock ParsedStdInfo 列表。"""
    parsed_a = MagicMock()
    parsed_a.get_full_number.return_value = "GB/T 1-2020"
    parsed_a.std_name = "基础规范"
    parsed_a.__str__.return_value = "GB/T 1-2020"
    parsed_b = MagicMock()
    parsed_b.get_full_number.return_value = "SH/T 2-2010"
    parsed_b.std_name = "化工标准"
    parsed_b.__str__.return_value = "SH/T 2-2010"
    return [parsed_a, parsed_b]


class TestPendingQueryDialog:
    """待确认二次查询对话框测试。"""

    def test_dialog_creates_with_title(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """对话框正常创建并设置窗口标题。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() != ""
        assert dlg.minimumWidth() >= 400

    def test_dialog_has_site_radio_buttons(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """对话框包含站点单选按钮。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        assert len(dlg._radio_group) >= 2  # site_a + site_b
        assert "site_a" in dlg._radio_group
        assert "site_b" in dlg._radio_group

    def test_start_without_selection_shows_warning(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """未选站点点击开始弹出警告对话框。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        # 确保没有按钮被选中
        for rb in dlg._radio_group.values():
            rb.setChecked(False)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok) as mock_warn:
            dlg._on_start()
            mock_warn.assert_called_once()

    def test_local_db_detection_disabled(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """公告数据库默认未开启时不显示本地数据库选项。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        with patch("pilotstd.ui.pending_query_dialog.ConfigManager") as mock_cfg:
            mock_cfg_instance = MagicMock()
            mock_cfg_instance.get.return_value = False
            mock_cfg.return_value = mock_cfg_instance

            dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
            qtbot.addWidget(dlg)
            assert dlg._has_local_db is False
            assert PendingQueryDialog.LOCAL_DB_KEY not in dlg._radio_group

    def test_local_db_detection_enabled(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """公告数据库已开启时显示本地数据库选项。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        with patch("pilotstd.ui.pending_query_dialog.ConfigManager") as mock_cfg:
            mock_cfg_instance = MagicMock()
            mock_cfg_instance.get.return_value = True
            mock_cfg.return_value = mock_cfg_instance

            dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
            qtbot.addWidget(dlg)
            assert dlg._has_local_db is True

    def test_dialog_cleanup_on_reject(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """对话框关闭时 timer 被停止。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg.reject()
        assert dlg._refresh_timer.isActive() is False

    def test_get_results_returns_list(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """get_results 返回结果列表（初始为空）。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        results = dlg.get_results()
        assert isinstance(results, list)
        assert results == []
