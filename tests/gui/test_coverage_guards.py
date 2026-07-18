"""测试 MainWindow 中各 parts 模块的 guard 分支和其他未覆盖行。

覆盖目标：
  - _delegate_ops.py: _require_core 的 None guard 分支
  - _download_ops.py: _mgr_ready guard + 下载队列逻辑
  - _file_dialog_ops.py: 文件/文件夹选择分支
  - _ui_setup_ops.py: signal 注册异常吞没 + NotificationAggregator.shutdown 异常吞没
  - _persistence_ops.py: _core 就绪时的 PersistenceHandler 委托路径
"""

from unittest.mock import MagicMock, patch

# ════════════════════════════════════════════════════════════════════
# Helper: 临时设置 _core=None 并自动恢复，避免 teardown 崩溃
# ════════════════════════════════════════════════════════════════════


class _core_guard:
    """上下文管理器：将 window._core 临时置为 mock（含 announce 属性），测试完成后恢复。"""

    def __init__(self, window):
        self._window = window
        self._saved = None

    def __enter__(self):
        self._saved = self._window._core
        mock_core = MagicMock()
        self._window._core = mock_core
        return mock_core

    def __exit__(self, *args):
        self._window._core = self._saved


class _core_null:
    """上下文管理器：将 window._core 临时置为 None，测试完成后恢复。"""

    def __init__(self, window):
        self._window = window
        self._saved = None

    def __enter__(self):
        self._saved = self._window._core
        self._window._core = None
        return None

    def __exit__(self, *args):
        self._window._core = self._saved


# ════════════════════════════════════════════════════════════════════
# 任务 1：_delegate_ops.py — _require_core guard 分支
# ════════════════════════════════════════════════════════════════════


class TestDelegateOpsGuards:
    def test_require_core_returns_false_when_core_is_none(self, window):
        from pilotstd.ui.main_window.parts._delegate_ops import _require_core

        with _core_null(window):
            assert _require_core(window) is False

    def test_on_check_announcements_guard(self, window):
        with _core_null(window):
            window._on_check_announcements()

    def test_on_download_guard(self, window):
        with _core_null(window):
            window._on_download()

    def test_on_import_download_guard(self, window):
        with _core_null(window):
            window._on_import_download()

    def test_run_scan_guard(self, window):
        with _core_null(window):
            window._run_scan("dummy")

    def test_on_query_guard(self, window):
        with _core_null(window):
            window._on_query()

    def test_on_save_to_folder_guard(self, window):
        with _core_null(window):
            window._on_save_to_folder()

    def test_on_normalize_guard(self, window):
        with _core_null(window):
            window._on_normalize()

    def test_start_auto_pipeline_guard(self, window):
        with _core_null(window):
            window._start_auto_pipeline("dummy")

    def test_on_cleanup_empty_dirs_guard(self, window):
        with _core_null(window):
            window._on_cleanup_empty_dirs()

    def test_on_collect_unrecognized_guard(self, window):
        with _core_null(window):
            window._on_collect_unrecognized()


# ════════════════════════════════════════════════════════════════════
# 任务 2：_download_ops.py
# ════════════════════════════════════════════════════════════════════


class TestDownloadOps:
    def test_check_download_queue_mgr_not_ready(self, window):
        window._mgr_ready = False
        window._check_download_queue()

    def test_check_download_queue_with_due(self, window):
        window._mgr_ready = True
        due_items = [
            {"standard_number": "GB/T 1.1-2020"},
            {"standard_number": "ISO 9001:2015"},
        ]
        window._mgr.get_due_downloads = MagicMock(return_value=due_items)
        window._mgr.remove_download_queue = MagicMock()
        window._on_download = MagicMock()

        window._check_download_queue()

        window._mgr.remove_download_queue.assert_any_call("GB/T 1.1-2020")
        window._mgr.remove_download_queue.assert_any_call("ISO 9001:2015")
        window._on_download.assert_called_once()

    def test_on_auto_run_mgr_not_ready(self, window):
        window._mgr_ready = False
        window._on_auto_run()

    def test_on_auto_run_with_path(self, window):
        window._mgr_ready = True
        window._menu_selected_path = "/test/path"
        window._start_auto_pipeline = MagicMock()
        window._on_auto_run()
        window._start_auto_pipeline.assert_called_once_with("/test/path")


# ════════════════════════════════════════════════════════════════════
# 任务 3：_file_dialog_ops.py
# ════════════════════════════════════════════════════════════════════


class TestFileDialogOps:
    def test_on_open_file_with_selection(self, window, qtbot):
        mock_path = "/mock/selected/file.pdf"
        window._run_scan = MagicMock()

        with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=(mock_path, "")):
            window._on_open_file()

        assert window._menu_selected_path == mock_path
        window._run_scan.assert_called_once_with(mock_path)

    def test_on_open_folder_with_selection(self, window):
        mock_path = "/mock/folder"
        window._pick_folder = MagicMock(return_value=mock_path)
        window._run_scan = MagicMock()

        window._on_open_folder()

        assert window._menu_selected_path == mock_path
        window._run_scan.assert_called_once_with(mock_path)

    def test_on_select_with_selection(self, window):
        mock_path = "/mock/select_folder"
        window._pick_folder = MagicMock(return_value=mock_path)
        window._run_scan = MagicMock()

        window._on_select()

        assert window._menu_selected_path == mock_path
        window._run_scan.assert_called_once_with(mock_path)


# ════════════════════════════════════════════════════════════════════
# 任务 4：_ui_setup_ops.py — 异常吞没分支
# ════════════════════════════════════════════════════════════════════


class TestUiSetupOpsExceptionHandling:
    def test_setup_auto_save_signal_failure_is_suppressed(self, window):
        with patch("signal.signal", side_effect=ValueError("不允许在此线程设置信号处理")):
            window._setup_auto_save()

    def test_on_shutdown_aggregator_exception_suppressed(self, window):
        with patch("pilotstd.core.notification_aggregator.NotificationAggregator") as mock_agg_class:
            mock_instance = MagicMock()
            mock_instance.shutdown.side_effect = RuntimeError("shutdown 失败")
            mock_agg_class.return_value = mock_instance
            window._on_shutdown_aggregator()


# ════════════════════════════════════════════════════════════════════
# 任务 5：_persistence_ops.py — _core 就绪时 PersistenceHandler 路径
# ════════════════════════════════════════════════════════════════════


class TestPersistenceOpsWithCore:
    def test_restore_window_geometry_delegates_to_handler(self, window):
        with _core_guard(window) as mock_core:
            mock_persistence = MagicMock()
            mock_core.persistence = mock_persistence
            window._restore_window_geometry()
            mock_persistence.restore_window_geometry.assert_called_once_with(window)

    def test_restore_splitter_sizes_delegates_to_handler(self, window):
        with _core_guard(window) as mock_core:
            mock_persistence = MagicMock()
            mock_core.persistence = mock_persistence
            window._restore_splitter_sizes()
            mock_persistence.restore_splitter_sizes.assert_called_once_with(
                window._main_splitter, window._right_splitter
            )

    def test_restore_sort_state_delegates_to_handler(self, window):
        with _core_guard(window) as mock_core:
            mock_persistence = MagicMock()
            mock_core.persistence = mock_persistence
            window._restore_sort_state()
            mock_persistence.restore_sort_state.assert_called_once_with(window.work_table)

    def test_restore_column_widths_delegates_to_handler(self, window):
        with _core_guard(window) as mock_core:
            mock_persistence = MagicMock()
            mock_core.persistence = mock_persistence
            window._restore_column_widths()
            mock_persistence.restore_column_widths.assert_called_once_with(window.work_table)

    def test_on_open_project_delegates_to_handler(self, window):
        with _core_guard(window) as mock_core:
            mock_project = MagicMock()
            mock_core.project = mock_project
            window._on_open_project()
            mock_project.on_open_project.assert_called_once()

    def test_on_save_query_project_delegates_to_handler(self, window):
        with _core_guard(window) as mock_core:
            mock_project = MagicMock()
            mock_core.project = mock_project
            window._on_save_query_project()
            mock_project.on_save_query_project.assert_called_once()

    def test_on_save_download_project_delegates_to_handler(self, window):
        with _core_guard(window) as mock_core:
            mock_project = MagicMock()
            mock_core.project = mock_project
            window._on_save_download_project()
            mock_project.on_save_download_project.assert_called_once()
