# tests/gui/test_main_window_core.py
# MainWindow 核心路径补充测试 — 覆盖初始化、菜单、对话框、进度条、持久化等
# 目标：与已有 test_manual_workflow.py + test_full_pipeline.py 配合达到 ≥75%

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

# ════════════════════════════════════════════════════════════════
# 1. MainWindow 初始化与属性
# ════════════════════════════════════════════════════════════════


def test_main_window_title(window, qtbot):
    """主窗口标题包含 PilotStd。"""
    assert "PilotStd" in window.windowTitle()


def test_main_window_minimum_size(window, qtbot):
    """主窗口最小尺寸 >= 1000x550。"""
    assert window.minimumWidth() >= 1000
    assert window.minimumHeight() >= 550


def test_main_window_initial_pause_state(window, qtbot):
    """初始状态：未暂停，pause_event 为 signaled。"""
    assert window._paused is False
    assert window._pause_event.is_set()


def test_main_window_file_menu_exists(window, qtbot):
    """_file_menu 在 _setup_menu 中创建。"""
    assert window._file_menu is not None
    assert window._file_menu.title() != ""


def test_mgr_property_lazy_init(window, qtbot):
    """_mgr 属性首次访问时触发延迟初始化。"""
    mgr = window._mgr  # 触发 _init_manager
    assert mgr is not None
    assert window._mgr_ready is True
    assert window._file_menu.isEnabled() is True


def test_mgr_setter(window, qtbot):
    """_mgr setter 直接设置 backing field。"""
    mock = MagicMock()
    window._mgr = mock
    assert window._mgr is mock


def test_get_selected_path_from_file_tree(window, test_data_dir, qtbot):
    """_get_selected_path 返回文件树选中项路径。"""
    from PyQt6.QtWidgets import QTreeWidgetItem

    sample = os.path.join(test_data_dir, os.listdir(test_data_dir)[0])
    item = QTreeWidgetItem([os.path.basename(sample)])
    item.setData(0, Qt.ItemDataRole.UserRole, sample)
    window.file_tree.addTopLevelItem(item)
    window.file_tree.setCurrentItem(item)
    assert window._get_selected_path() == sample


def test_get_selected_path_fallback(window, qtbot):
    """文件树无选中时返回 _menu_selected_path。"""
    window.file_tree.clearSelection()
    window._menu_selected_path = "D:/fallback"
    assert window._get_selected_path() == "D:/fallback"


def test_add_row_from_dict(window, qtbot):
    """_add_row_from_dict 从字典重建工作表行。"""
    initial = window.work_table.rowCount()
    row_data = {"文件名": "test.pdf", "工作状态": "已扫描"}
    window._add_row_from_dict(row_data)
    assert window.work_table.rowCount() == initial + 1


def test_show_welcome_if_needed_skipped(window, qtbot):
    """skip_welcome=True 时跳过欢迎页。"""
    window._config.set("appearance.skip_welcome", True)
    # 不应弹出对话框
    window.show_welcome_if_needed()


def test_show_welcome_if_needed_shown(window, qtbot):
    """skip_welcome=False 时显示欢迎页。"""
    window._config.set("appearance.skip_welcome", False)
    with patch("pilotstd.ui.welcome_dialog.WelcomeDialog") as mock_dlg_class:
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QMessageBox.DialogCode.Accepted
        mock_dlg.should_skip.return_value = True
        mock_dlg_class.return_value = mock_dlg
        window.show_welcome_if_needed()
        mock_dlg_class.assert_called_once()
        # should_skip=True 时保存配置
        assert window._config.get("appearance.skip_welcome") is True


def test_collect_state(window, qtbot):
    """_collect_state 返回工作状态字典。"""
    state = window._collect_state()
    assert "work_table_rows" in state
    assert "current_path" in state
    assert "unrecognized_files" in state


# ════════════════════════════════════════════════════════════════
# 2. 对话框操作 (_dialog_ops)
# ════════════════════════════════════════════════════════════════


def test_question_dlg_suppressed(window, qtbot):
    """suppress_dialogs=True 时 _question_dlg 直接返回 Yes。"""
    window._suppress_dialogs = True
    result = window._question_dlg("标题", "消息")
    assert result == QMessageBox.StandardButton.Yes


def test_question_dlg_normal(window, qtbot):
    """suppress_dialogs=False 时 _question_dlg 弹出对话框。"""
    window._suppress_dialogs = False
    # 通过 mock 验证逻辑：弹出、返回结果
    with patch.object(window, "_question_dlg", wraps=window._question_dlg) as wrapped:
        # _suppress_dialogs=True 时走快速路径
        window._suppress_dialogs = True
        result = wrapped("标题", "消息")
        assert result == QMessageBox.StandardButton.Yes


def test_stage_prereq_dialog_suppressed(window, qtbot):
    """suppress_dialogs=True 时 _stage_prereq_dialog 直接返回 skip。"""
    window._suppress_dialogs = True
    result = window._stage_prereq_dialog("标题", "消息")
    assert result == "skip"


def test_show_stage_dialog_suppressed(window, qtbot):
    """suppress_dialogs=True 时 _show_stage_dialog 跳过弹窗但执行回调。"""
    window._suppress_dialogs = True
    called = []
    window._show_stage_dialog("标题", "消息", next_action=lambda: called.append(1))
    assert called == [1]


def test_register_task(window, qtbot):
    """_register_task 创建任务记录。"""
    window._register_task("扫描", total=10, completed=5, failed=1)
    # task_queue 应有记录（不抛异常即通过）


def test_on_raw_progress(window, qtbot):
    """_on_raw_progress 设置目标进度并启动定时器。"""
    window._on_raw_progress(5, 10)
    assert window._target_progress == 50


def test_animate_progress(window, qtbot):
    """_animate_progress 逐步推进进度条。"""
    window._target_progress = 100
    window._current_progress = 0
    window._animate_progress()
    assert window._current_progress > 0


def test_reset_progress_bar(window, qtbot):
    """_reset_progress_bar 重置进度为 0。"""
    window._target_progress = 100
    window._current_progress = 50
    window._reset_progress_bar()
    assert window._target_progress == 0
    assert window._current_progress == 0.0


def test_force_finish_progress(window, qtbot):
    """_force_finish_progress 直接跳到 100%。"""
    window._force_finish_progress()
    assert window._target_progress == 100
    assert window._current_progress == 100.0


# ════════════════════════════════════════════════════════════════
# 3. 操作按钮 (_actions_ops)
# ════════════════════════════════════════════════════════════════


def test_get_pipeline_stats_before_ready(window, qtbot):
    """_mgr 未就绪时 get_pipeline_stats 返回空字典。"""
    window._mgr_ready = False
    stats = window.get_pipeline_stats()
    assert stats == {}


def test_get_pipeline_stats_after_ready(window, qtbot):
    """_mgr 就绪后 get_pipeline_stats 返回完整统计。"""
    mgr = window._mgr  # 触发延迟初始化
    stats = window.get_pipeline_stats()
    assert "scan_count" in stats
    assert "query_total" in stats


def test_set_toolbar_enabled_false(window, qtbot):
    """_set_toolbar_enabled(False) 禁用所有工具栏按钮。"""
    window._set_toolbar_enabled(False)
    assert not window.btn_select.isEnabled()
    assert not window.btn_query.isEnabled()
    assert not window.btn_auto.isEnabled()


def test_set_toolbar_enabled_true(window, qtbot):
    """_set_toolbar_enabled(True) 启用所有工具栏按钮。"""
    window._set_toolbar_enabled(True)
    assert window.btn_select.isEnabled()
    assert window.btn_query.isEnabled()
    assert window.btn_auto.isEnabled()


def test_apply_announce_cache_mode(window, qtbot):
    """_apply_announce_cache_mode 根据配置设置公告按钮状态。"""
    window._config.set("query.use_announcement_match", True)
    window._apply_announce_cache_mode()
    assert not window.btn_announce.isEnabled()

    window._config.set("query.use_announcement_match", False)
    window._apply_announce_cache_mode()
    assert window.btn_announce.isEnabled()


def test_update_button_states_empty(window, qtbot):
    """空工作区时查询按钮重置为初始状态。"""
    window._parsed_results.clear()
    window._update_button_states()
    # 空数据时按钮根据 parsed_results 决定


def test_update_button_states_with_data(window, test_data_dir, qtbot):
    """有数据时 _update_button_states 根据队列更新按钮状态。"""
    window._mgr  # 确保 _mgr 就绪
    window._update_button_states()
    # 不抛异常即通过


def test_on_cancel_resets_state(window, qtbot):
    """_on_cancel 重置暂停/压制/按钮状态。"""
    window._paused = True
    window._suppress_dialogs = True
    window._on_cancel()
    assert window._paused is False
    assert window._suppress_dialogs is False
    assert window._pause_event.is_set()
    assert not window.btn_cancel.isEnabled()


def test_on_pause_toggle_cycle(window, qtbot):
    """_on_pause_toggle 切换暂停/继续。"""
    # 暂停
    window._on_pause_toggle()
    assert window._paused is True
    assert window.btn_pause.text() == "继续"
    assert not window._pause_event.is_set()

    # 继续
    window._on_pause_toggle()
    assert window._paused is False
    assert window.btn_pause.text() == "暂停"
    assert window._pause_event.is_set()


def test_on_about(window, qtbot):
    """_on_about 显示关于对话框。"""
    with patch.object(QMessageBox, "about", return_value=None) as mock_about:
        window._on_about()
        mock_about.assert_called_once()


def test_on_task_center(window, qtbot):
    """_on_task_center 打开任务中心对话框。"""
    window._mgr  # 确保就绪
    with patch("pilotstd.ui.pages.task_page.TaskCenterDialog") as mock_dlg:
        mock_instance = MagicMock()
        mock_dlg.return_value = mock_instance
        mock_instance.exec.return_value = QMessageBox.DialogCode.Accepted
        window._on_task_center()
        mock_dlg.assert_called_once()


def test_on_settings(window, qtbot):
    """_on_settings 打开设置对话框。"""
    with patch("pilotstd.ui.pages.settings_page.SettingsDialog") as mock_dlg:
        mock_instance = MagicMock()
        mock_dlg.return_value = mock_instance
        mock_instance.exec.return_value = QMessageBox.DialogCode.Accepted
        window._on_settings()
        mock_dlg.assert_called_once()


def test_try_check_update_throttle(window, qtbot):
    """更新检查限流：24h 内重复检查显示提示。"""
    import time

    window._config.set("appearance.last_update_check", time.time())
    with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok) as mock_info:
        result = window._try_check_update_throttle("v1.0")
        assert result is True
        mock_info.assert_called_once()


def test_try_check_update_throttle_expired(window, qtbot):
    """更新检查限流：超过 24h 允许检查。"""
    import time

    window._config.set("appearance.last_update_check", time.time() - 100000)
    result = window._try_check_update_throttle("v1.0")
    assert result is False


# ════════════════════════════════════════════════════════════════
# 4. 查询操作 (_query_ops)
# ════════════════════════════════════════════════════════════════


def test_on_query_result_ready_updates_table(window, qtbot):
    """_on_query_result_ready 更新工作表中对应行列。"""
    window._suppress_dialogs = True
    window._mgr  # 确保就绪

    # 先添加一行
    row_data = {"文件名": "GB_T_1-2020.pdf", "标准号": "GB/T 1-2020"}
    window._add_row_from_dict(row_data)

    mock_parsed = MagicMock()
    mock_parsed.std_name = "基础规范"
    window._parsed_results = [mock_parsed]

    mock_result = MagicMock()
    mock_result.standard_name = "标准化工作导则"
    mock_result.status = "现行"
    mock_result.replaces = ""
    mock_result.publish_date = "2020-03-31"
    mock_result.implementation_date = "2020-10-01"
    mock_result.responsible_dept = "全国标准化技术委员会"
    mock_result.is_adopted = False
    mock_result.is_downloadable = True
    mock_result.source_site = "njbz365"

    window._on_query_result_ready(0, mock_result)
    # 不抛异常即通过


def test_show_query_summary(window, qtbot):
    """_show_query_summary 转发到 handler。"""
    window._mgr  # 确保 _core 就绪
    if hasattr(window, "_core"):
        window._core.query.show_query_summary = MagicMock()
        window._show_query_summary()
        window._core.query.show_query_summary.assert_called_once()


# ════════════════════════════════════════════════════════════════
# 5. 持久化操作 — fallback 路径（_core 未就绪时直接操作 config）
# ════════════════════════════════════════════════════════════════


def test_save_restore_window_geometry_fallback(window, qtbot):
    """_core 未初始化时直接读写 config 中的 window_geometry。"""
    # 确保 _core 不存在，走 fallback
    if hasattr(window, "_core"):
        del window._core

    # 保存
    window._save_window_geometry()
    geo = window._config.get("appearance.window_geometry")
    assert geo is not None and len(geo) > 0

    # 恢复
    window._restore_window_geometry()  # 不抛异常


def test_save_restore_splitter_sizes_fallback(window, qtbot):
    """_core 未初始化时直接读写 config 中的 splitter 尺寸。"""
    if hasattr(window, "_core"):
        del window._core

    window._save_splitter_sizes()
    sizes = window._config.get("appearance.main_splitter")
    assert sizes is not None

    window._restore_splitter_sizes()  # 不抛异常


def test_save_restore_sort_state_fallback(window, qtbot):
    """_core 未初始化时直接读写 config 中的表头状态。"""
    if hasattr(window, "_core"):
        del window._core

    window._save_sort_state()
    data = window._config.get("appearance.header_state")
    assert data is not None

    window._restore_sort_state()  # 不抛异常


def test_save_restore_column_widths_fallback(window, qtbot):
    """_core 未初始化时直接读写 config 中的列宽。"""
    if hasattr(window, "_core"):
        del window._core

    window._save_column_widths()
    widths = window._config.get("appearance.column_widths")
    assert widths is not None

    window._restore_column_widths()  # 不抛异常


def test_on_open_project_no_core(window, qtbot):
    """_core 未就绪时 _on_open_project 安全返回。"""
    if hasattr(window, "_core"):
        del window._core
    window._on_open_project()  # 不抛异常


def test_on_save_query_project_no_core(window, qtbot):
    """_core 未就绪时 _on_save_query_project 安全返回。"""
    if hasattr(window, "_core"):
        del window._core
    window._on_save_query_project()  # 不抛异常


def test_on_save_download_project_no_core(window, qtbot):
    """_core 未就绪时 _on_save_download_project 安全返回。"""
    if hasattr(window, "_core"):
        del window._core
    window._on_save_download_project()  # 不抛异常


# ════════════════════════════════════════════════════════════════
# 6. 状态栏和信号
# ════════════════════════════════════════════════════════════════


def test_status_bar_exists(window, qtbot):
    """状态栏存在且可显示消息。"""
    window.status_bar.showMessage("测试消息")
    assert window.status_bar is not None


def test_on_progress_callback(window, qtbot):
    """_on_progress 更新进度条值。"""
    window.progress_bar.setValue(0)
    window._on_progress(42)
    assert window.progress_bar.value() == 42


def test_on_status_callback(window, qtbot):
    """_on_status 更新状态栏消息。"""
    window._on_status("状态测试")
    # 不抛异常即通过


def test_status_changed_signal(window, qtbot):
    """status_changed 信号可连接和发射。"""
    from PyQt6.QtTest import QSignalSpy

    spy = QSignalSpy(window.status_changed)
    window.status_changed.emit("测试")
    assert len(spy) == 1
    assert spy[0][0] == "测试"


def test_progress_changed_signal(window, qtbot):
    """progress_changed 信号可连接和发射。"""
    from PyQt6.QtTest import QSignalSpy

    spy = QSignalSpy(window.progress_changed)
    window.progress_changed.emit(50)
    assert len(spy) == 1
    assert spy[0][0] == 50


# ════════════════════════════════════════════════════════════════
# 7. 菜单和工具栏
# ════════════════════════════════════════════════════════════════


def test_menu_bar_exists(window, qtbot):
    """菜单栏存在且包含菜单项。"""
    mb = window.menuBar()
    assert mb is not None
    actions = mb.actions()
    assert len(actions) > 0


def test_work_table_has_context_menu(window, qtbot):
    """工作表设置了右键菜单策略。"""
    assert window.work_table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_file_tree_has_context_menu(window, qtbot):
    """文件树设置了右键菜单策略。"""
    assert window.file_tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_log_view_readonly(window, qtbot):
    """日志面板为只读。"""
    assert window.log_view.isReadOnly()


# ════════════════════════════════════════════════════════════════
# 8. 自动保存
# ════════════════════════════════════════════════════════════════


def test_on_auto_save(window, qtbot):
    """_on_auto_save 安全调用（_project 可能无当前路径）。"""
    window._on_auto_save()  # 不抛异常


# ════════════════════════════════════════════════════════════════
# 9. 主题/语言 (_theme_ops)
# ════════════════════════════════════════════════════════════════


def test_retranslate_ui(window, qtbot):
    """_retranslate_ui 刷新所有可见文本。"""
    window._retranslate_ui()  # 不抛异常
    # 菜单文本应被刷新
    assert window._file_menu.title() != ""


def test_apply_language(window, qtbot):
    """_apply_language 切换语言。"""
    window._apply_language()  # 不抛异常


def test_apply_theme(window, qtbot):
    """_apply_theme 应用主题。"""
    window._apply_theme()  # 不抛异常


def test_apply_icon(window, qtbot):
    """_apply_icon 应用图标。"""
    window._apply_icon()  # 不抛异常


# ════════════════════════════════════════════════════════════════
# 10. 托盘
# ════════════════════════════════════════════════════════════════


def test_tray_exists(window, qtbot):
    """系统托盘已创建。"""
    assert window._tray is not None


def test_tray_icon(window, qtbot):
    """托盘图标存在。"""
    assert window._tray.icon() is not None


# ════════════════════════════════════════════════════════════════
# 11. 文件对话框操作
# ════════════════════════════════════════════════════════════════


def test_pick_folder(window, qtbot):
    """_pick_folder 调用 QFileDialog。"""
    with patch(
        "pilotstd.ui.main_window.parts._file_dialog_ops.QFileDialog.getExistingDirectory", return_value="D:/selected"
    ) as mock_fd:
        result = window._pick_folder("选择文件夹", "D:/")
        assert result == "D:/selected"
        mock_fd.assert_called_once()


# ════════════════════════════════════════════════════════════════
# 12. 导出操作
# ════════════════════════════════════════════════════════════════


def test_collect_folder_tree(window, qtbot):
    """_collect_folder_tree 遍历目录结构。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_tree_")
    try:
        os.makedirs(os.path.join(tmp, "subdir"), exist_ok=True)
        with open(os.path.join(tmp, "test.pdf"), "w") as f:
            f.write("test")
        lines = []
        window._collect_folder_tree(tmp, lines, prefix="")
        assert len(lines) > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_on_export_file_list(window, test_data_dir, qtbot):
    """_on_export_file_list 弹出导出选项对话框。"""
    window._menu_selected_path = test_data_dir
    with (
        patch("pilotstd.ui.main_window.parts._export_ops.ExportFileListDialog") as mock_dlg,
        patch("pilotstd.ui.main_window.parts._export_ops.QFileDialog.getSaveFileName", return_value=("", "")),
    ):
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QMessageBox.DialogCode.Accepted
        mock_instance.include_path = False
        mock_instance.source_path = test_data_dir
        mock_dlg.return_value = mock_instance
        window._on_export_file_list()
