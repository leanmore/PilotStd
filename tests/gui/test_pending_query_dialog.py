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
    parsed_a.__str__.return_value = "GB/T 1-2020"  # type: ignore[attr-defined]
    parsed_b = MagicMock()
    parsed_b.get_full_number.return_value = "SH/T 2-2010"
    parsed_b.std_name = "化工标准"
    parsed_b.__str__.return_value = "SH/T 2-2010"  # type: ignore[attr-defined]
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

        with patch("pilotstd.core.config.ConfigManager") as mock_cfg:
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

        with patch("pilotstd.core.config.ConfigManager") as mock_cfg:
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

    # ── 补充覆盖：查询流程、冷却、重试计数等 ──

    def test_on_start_requery_exhausted(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """重试次数已耗尽时弹出警告并返回。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.is_requery_exhausted.return_value = True
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        # 选中第一个站点
        dlg._radio_group["site_a"].setChecked(True)

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok) as mock_warn:
            dlg._on_start()
            mock_warn.assert_called_once()

    def test_on_start_requery_count_warn_yes(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """重试 2 次后用户确认继续——弹出询问框，选 Yes 进入查询。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.get_requery_count.return_value = 2
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._radio_group["site_a"].setChecked(True)

        with (
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_q,
            patch.object(dlg, "_do_query") as mock_do,
        ):
            dlg._on_start()
            # 两个已解析项各触发一次询问
            assert mock_q.call_count == 2
            mock_do.assert_called_once()

    def test_on_start_requery_count_warn_no(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """重试 2 次后用户取消——弹出询问框，选 No 返回。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.get_requery_count.return_value = 2
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._radio_group["site_a"].setChecked(True)

        with (
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as mock_q,
            patch.object(dlg, "_do_query") as mock_do,
        ):
            dlg._on_start()
            mock_q.assert_called_once()
            mock_do.assert_not_called()

    def test_on_start_local_db(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """选择本地数据库时直接走 _do_local_query。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._has_local_db = True
        dlg._radio_group[PendingQueryDialog.LOCAL_DB_KEY] = MagicMock()
        dlg._radio_group[PendingQueryDialog.LOCAL_DB_KEY].isChecked.return_value = True  # type: ignore[attr-defined]

        with patch.object(dlg, "_do_local_query") as mock_local:
            dlg._on_start()
            mock_local.assert_called_once()

    def test_on_start_with_cooldown(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """选中站点有冷却时进入倒计时等待。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.get_site_cooldown.return_value = 300  # 5 分钟冷却
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._radio_group["site_a"].setChecked(True)

        dlg._on_start()
        assert dlg._countdown_active is True
        assert dlg._start_btn.isEnabled() is False

    def test_on_start_long_cooldown_shows_info(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """超过 4 小时冷却时弹出提示信息。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.get_site_cooldown.return_value = 18000  # 5 小时
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._radio_group["site_a"].setChecked(True)

        with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok) as mock_info:
            dlg._on_start()
            mock_info.assert_called_once()

    def test_do_local_query(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """本地数据库查询：调用 manager.query_local_cache，完成后弹窗。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.query_local_cache.return_value = [
            (0, MagicMock(standard_name="GB/T 1-2020")),
            (1, MagicMock(standard_name="")),
        ]
        mock_manager.increment_requery_count.return_value = 0
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)

        with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok) as mock_info:
            dlg._do_local_query()
            mock_manager.query_local_cache.assert_called_once_with(mock_parsed_list)
            mock_info.assert_called_once()

    def test_on_single_result_updates_progress(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """每条结果回调更新进度条和结果列表。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)

        mock_result = MagicMock()
        mock_result.standard_name = "测试标准"
        dlg._on_single_result(0, mock_result)
        assert len(dlg._results) == 1
        assert dlg._progress.value() == 1

    def test_on_query_finished_accumulates(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """查询完成：统计成功/失败，更新重试计数，弹窗，accept。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._results = [
            (0, MagicMock(standard_name="GB/T 1-2020")),
            (1, MagicMock(standard_name="")),  # 空标准名视为未找到
        ]
        mock_manager.increment_requery_count.return_value = 0

        with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok) as mock_info:
            dlg._on_query_finished(None)
            # 失败的那个应递增重试计数
            mock_manager.increment_requery_count.assert_called_once()
            mock_info.assert_called_once()
        assert dlg.result() == 1  # accept

    def test_refresh_cooldown_disables_cooling_sites(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """冷却中的站点单选按钮被禁用并显示冷却时间。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.get_site_cooldown.side_effect = lambda name: 120 if name == "site_a" else 0
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._refresh_cooldown()

        assert dlg._radio_group["site_a"].isEnabled() is False
        assert dlg._cooldown_labels["site_a"].text() != ""
        assert dlg._radio_group["site_b"].isEnabled() is True

    def test_refresh_cooldown_auto_trigger(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """冷却结束后自动触发查询。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.get_site_cooldown.return_value = 0
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._countdown_active = True
        dlg._selected_site = "site_a"

        with patch.object(dlg, "_do_query") as mock_do:
            dlg._refresh_cooldown()
            assert dlg._countdown_active is False
            mock_do.assert_called_once()

    def test_close_event_cleanup(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """closeEvent 调用 _cleanup 停止 timer。"""
        from PyQt6.QtGui import QCloseEvent

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg.closeEvent(QCloseEvent())
        assert dlg._refresh_timer.isActive() is False

    def test_check_local_db_configmanager_error(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """ConfigManager 异常时 _has_local_db 为 False 不崩溃。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        with patch("pilotstd.core.config.ConfigManager", side_effect=RuntimeError("boom")):
            dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
            qtbot.addWidget(dlg)
            assert dlg._has_local_db is False

    def test_notify_error_with_notification_mgr(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """Worker 异常时通过 notification_mgr 发送事件。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.notification_mgr = MagicMock()
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._notify_error("query_pending", "测试错误")
        mock_manager.notification_mgr.send_event.assert_called_once()

    def test_notify_error_no_notification_mgr(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """没有 notification_mgr 时 _notify_error 静默处理。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.notification_mgr = None
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        # 不应抛出异常
        dlg._notify_error("query_pending", "测试错误")

    def test_worker_cleanup_on_reject(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """reject 时若有运行中的 worker：先断业务信号，再协作式停止，绝不 terminate。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.wait.return_value = True
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._worker = mock_worker
        dlg.reject()
        mock_worker.stop.assert_called_once()
        mock_worker.requestInterruption.assert_called_once()
        mock_worker.result_ready.disconnect.assert_called_once()
        mock_worker.wait.assert_called_once_with(3000)
        assert mock_worker.terminate.call_count == 0, "严禁用 terminate() 强杀线程"

    def test_do_query_adapter_not_found(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """查询站点适配器不存在时弹出错误对话框并 reject。"""
        from PyQt6.QtWidgets import QMessageBox

        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        mock_manager.query_engine.get_adapter.return_value = None
        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        dlg._radio_group["site_a"].setChecked(True)

        # patch QMessageBox.critical 避免创建真实弹窗导致 teardown 竞态
        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok):
            dlg._on_start()
        assert dlg.result() == 0  # reject

    def test_info_label_shows_count(self, qtbot, mock_manager, mock_parsed_list) -> None:
        """信息标签显示待确认标准数量。"""
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog

        dlg = PendingQueryDialog(mock_manager, mock_parsed_list)
        qtbot.addWidget(dlg)
        assert "2" in dlg.layout().itemAt(0).widget().text()  # type: ignore[union-attr]
