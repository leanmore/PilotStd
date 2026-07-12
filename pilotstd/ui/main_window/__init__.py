# pilotstd/ui/main_window/__init__.py
# 主窗口：菜单栏 + QToolBar + 左右分栏（文件浏览 | 工作区 | 日志）
#
# 架构说明：
#   主窗口是 PilotStd 的 UI 入口，负责协调所有前端组件。
#   布局采用三段式：顶部菜单栏+工具栏 / 中间左右分栏 / 底部状态栏。
#
#   屏幕空间分配：
#     左侧 200px：文件导航树（QTreeWidget，懒加载子目录）
#     中间 stretch：工作表（QTableWidget，显示扫描/查询/下载/归类结果）
#     右侧 240px：操作日志（QTextEdit，只读）
#
#   工作流（典型用户操作路径）：
#     扫描 → 查询 → 下载 → 规范化 → 归档（工具栏按钮依次驱动）
#     或一键自动运行（跳过中间确认对话框）
#
#   语言切换：
#     _apply_language() 加载 Qt 翻译文件 + 调用 _retranslate_ui() 刷新所有可见文本。
#     新增 UI 文字时必须在 _retranslate_ui() 中添加对应的 setText 调用。
#     QPushButton 初始文本可用 _() 直接包裹，工具栏按钮由 _retranslate_ui 统一管理。

import logging
import os
import threading
from typing import Any, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QTableWidgetItem

from ... import core
from ...i18n import _
from ..table_constants import WORK_COLUMN_KEYS, WORK_COLUMNS
from .parts._run_main import run as run

logger = logging.getLogger("pilotstd.ui")


class MainWindow(QMainWindow):
    # 信号：供外部模块更新进度
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    query_result_ready = pyqtSignal(int, object)

    # ── 导入方法片段（从 parts/ 注入，替代原 Mixin 内联）──

    from .parts._actions_ops import (
        _apply_announce_cache_mode,
        _check_pause,
        _confirm_update_available,
        _download_update_file,
        _init_manager,
        _on_about,
        _on_cancel,
        _on_check_update,
        _on_pause_toggle,
        _on_rule_download,
        _on_rule_query,
        _on_settings,
        _on_task_center,
        _prompt_restart,
        _set_toolbar_enabled,
        _switch_to_stage,
        _try_check_update_throttle,
        _update_button_states,
        get_pipeline_stats,
    )
    from .parts._delegate_ops import (
        _on_check_announcements,
        _on_cleanup_empty_dirs,
        _on_collect_unrecognized,
        _on_download,
        _on_import_download,
        _on_normalize,
        _on_query,
        _on_save_to_folder,
        _run_scan,
        _start_auto_pipeline,
    )
    from .parts._dialog_ops import (
        _animate_progress,
        _force_finish_progress,
        _on_raw_progress,
        _question_dlg,
        _register_task,
        _reset_progress_bar,
        _show_stage_dialog,
        _stage_prereq_dialog,
    )
    from .parts._download_ops import (
        _check_download_queue,
        _on_auto_run,
    )
    from .parts._export_ops import (
        _collect_folder_tree,
        _on_export_diag,
        _on_export_file_list,
        _on_export_folder_tree,
    )
    from .parts._file_dialog_ops import (
        _on_open_file,
        _on_open_folder,
        _on_select,
        _pick_folder,
    )
    from .parts._file_tree_ops import (
        _make_drive_item,
        _make_item,
        _navigate_to,
        _on_drives_ready,
        _on_file_tree_context_menu,
        _on_tree_item_expanded,
        _populate_children,
        _populate_quick_access,
    )
    from .parts._persistence_ops import (
        _on_open_project,
        _on_save_download_project,
        _on_save_query_project,
        _restore_column_widths,
        _restore_sort_state,
        _restore_splitter_sizes,
        _restore_window_geometry,
        _save_column_widths,
        _save_sort_state,
        _save_splitter_sizes,
        _save_window_geometry,
    )
    from .parts._query_ops import (
        _do_pending_query,
        _on_pending_query,
        _on_query_result_ready,
        _parse_pending_csv,
        _show_query_summary,
    )
    from .parts._table_ops import (
        _add_table_row,
        _apply_column_visibility,
        _clear_table,
        _copy_selected_cells,
        _enforce_min_column_width,
        _find_row_by_seq,
        _get_column_visibility,
        _get_visible_cols,
        _load_column_visibility,
        _on_header_context_menu,
        _on_offline_view,
        _on_save_result,
        _on_work_table_context_menu,
        _remove_selected_rows,
        _row_get,
        _save_column_visibility,
        _save_csv,
        _save_txt,
        _table_key_press_event,
        _table_to_list,
    )
    from .parts._theme_ops import (
        _apply_icon,
        _apply_language,
        _apply_theme,
        _load_qt_translator,
        _retranslate_ui,
    )
    from .parts._ui_setup_ops import (
        _on_shutdown_aggregator,
        _on_tray_activated,
        _setup_auto_save,
        _setup_central,
        _setup_file_tree,
        _setup_log_handler,
        _setup_log_panel,
        _setup_menu,
        _setup_scanner,
        _setup_status_bar,
        _setup_toolbar,
        _setup_tray,
        _setup_work_table,
    )

    def __init__(self, config: "core.ConfigManager", project: "core.ProjectManager") -> None:
        super().__init__()
        self._config = config
        self._project = project
        self._current_project_path: Optional[str] = None

        self.setWindowTitle("PilotStd — 标准文件管理工具")
        self._paused: bool = False  # 暂停状态（须在 _setup_log_handler 之前初始化）
        self._pause_event = threading.Event()  # 暂停事件，供 Worker 检查
        self._pause_event.set()  # 初始状态：未暂停，Event 须为 signaled
        self._apply_icon()
        self.setMinimumSize(1000, 550)
        self.resize(1000, 550)
        self._restore_window_geometry()
        self._menu_selected_path: str = ""  # 文件菜单选择的路径（独立于文件树）
        self._suppress_dialogs: bool = False  # 自动运行时抑制中间弹窗

        # Qt 翻译器须在控件创建前安装，否则内置右键菜单无法翻译
        self._load_qt_translator()

        self._setup_menu()
        self._file_menu.setEnabled(False)  # _core 就绪前禁用 File 菜单
        self._setup_toolbar()
        self._set_toolbar_enabled(False)  # 后端未就绪，工具栏置灰
        self._setup_central()
        self._setup_scanner()
        # ── 业务门面（唯一后端入口）──
        # 延迟初始化：__init__ 中仅设置占位，首次访问或 QTimer 触发时才创建
        self.__mgr: Any = None  # 私有 backing field，由 _mgr property 管理
        self._mgr_ready = False
        self._setup_status_bar()
        self._setup_log_handler()
        self._setup_auto_save()
        self._setup_tray()

        self.progress_changed.connect(self._on_progress)
        self.status_changed.connect(self._on_status)
        self.query_result_ready.connect(self._on_query_result_ready)

        # 进度条平滑动画（50ms 定时器，20FPS 缓动效果）
        self._target_progress = 0
        self._current_progress = 0.0
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(50)
        self._progress_timer.timeout.connect(self._animate_progress)

    # ── _mgr 延迟属性：首次访问时自动初始化 StandardManager ──

    @property
    def _mgr(self) -> Any:
        """业务门面延迟属性。未初始化时首次访问触发自动创建。"""
        if self.__mgr is None:
            self._init_manager()
        return self.__mgr

    @_mgr.setter
    def _mgr(self, value: Any) -> None:
        self.__mgr = value

    # ================================================================
    # 生命周期
    # ================================================================

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()

    def _quit_app(self) -> None:
        if self._mgr_ready:
            try:
                self._mgr.db.backup()
                logger.info("数据库已备份")
            except Exception:
                logger.debug("数据库备份跳过（DB未初始化或已关闭）")
            try:
                self._mgr.shutdown()
            except Exception:
                logger.debug("管理器关闭跳过")
        self._tray.hide()
        app = QApplication.instance()
        assert app is not None, "QApplication 未初始化"
        app.quit()

    def changeEvent(self, event: object) -> None:
        """窗口最小化时隐藏到系统托盘。"""
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self._save_window_geometry()
            self._save_splitter_sizes()
            self._save_sort_state()
            self._save_column_widths()
            self.hide()
            self._tray.showMessage(
                "PilotStd",
                _("tray_minimized_msg"),
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
            return
        super().changeEvent(event)

    def closeEvent(self, event: object) -> None:
        """关闭窗口时保存状态并退出。"""
        self._save_window_geometry()
        self._save_splitter_sizes()
        self._save_sort_state()
        self._save_column_widths()
        self._stop_workers()
        self._quit_app()
        event.accept()

    # ================================================================
    # Worker 管理
    # ================================================================

    def run_auto(self, source_dir: str) -> None:
        """供压力测试驱动器调用：启动统一 AutoWorker，异步返回。"""
        self._start_auto_pipeline(source_dir)

    def _stop_workers(self) -> None:
        # 先解除暂停，防止 Worker 卡在 _pause_event.wait() 中无法退出
        if hasattr(self, "_pause_event"):
            self._pause_event.set()
        # 已迁移到 Handler 的 Worker
        if hasattr(self, "_core"):
            self._core.announce.stop_workers()
            self._core.download.stop_workers()
            self._core.scan.stop_workers()
            self._core.query.stop_workers()
            self._core.archive.stop_workers()
            self._core.auto.stop_workers()
        for attr in ("_drive_thread",):
            try:
                w = getattr(self, attr, None)
                if w is not None and w.isRunning():
                    w.stop()
                    w.quit()
                    if not w.wait(5000):
                        w.terminate()
                        w.wait()
            except RuntimeError:
                pass

    # ================================================================
    # 自动保存
    # ================================================================

    def _on_auto_save(self) -> None:
        if self._mgr_ready:
            self._mgr.stop_watching()
        if self._project.current_path and self._project._dirty:
            state = self._collect_state()
            self._project.save(self._project.current_path, state)

    def _on_atexit_save(self) -> None:
        if self._project.current_path and self._project._dirty:
            state = self._collect_state()
            self._project.save(self._project.current_path, state)

    def _collect_state(self) -> dict[str, Any]:
        """收集当前工作状态供保存。"""
        return {
            "work_table_rows": self._table_to_list(),
            "current_path": self._project.current_path,
            "unrecognized_files": list(getattr(self, "_unrecognized_files", [])),
        }

    # ================================================================
    # 信号回调
    # ================================================================

    def _on_progress(self, value: int) -> None:
        logger.debug("进度条: %d%%", value)
        self.progress_bar.setValue(value)

    def _on_status(self, msg: str) -> None:
        self.status_bar.showMessage(msg)
        logger.info(msg)

    # ================================================================
    # 共享辅助
    # ================================================================

    def _get_selected_path(self) -> str:
        """获取当前工作路径：优先文件树选择，其次文件菜单选择的路径。"""
        items = self.file_tree.selectedItems()
        if items:
            path = items[0].data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.exists(str(path)):
                return str(path)
        return self._menu_selected_path

    def _add_row_from_dict(self, row_data: dict) -> None:
        """从字典重建工作表行（用于项目恢复）。"""
        row = self.work_table.rowCount()
        self.work_table.insertRow(row)
        for c, col_name in enumerate(WORK_COLUMNS):
            value = row_data.get(col_name, "")
            if not value:
                translated = _(WORK_COLUMN_KEYS[c])
                if translated != col_name:
                    value = row_data.get(translated, "")
            self.work_table.setItem(row, c, QTableWidgetItem(value))

    # ================================================================
    # 欢迎页
    # ================================================================

    def show_welcome_if_needed(self) -> None:
        skip = self._config.get("appearance.skip_welcome", False)
        if skip:
            return
        from ..welcome_dialog import WelcomeDialog  # 延迟导入

        dlg = WelcomeDialog(self)
        dlg.exec()
        if dlg.should_skip():
            self._config.set("appearance.skip_welcome", True)
            self._config.save()

    # ================================================================
    # UI 核心 Handler（组合模式，替代 Mixin 多重继承）
    # ================================================================

    def _init_core(self) -> None:
        """在 _mgr 就绪后初始化 UI 核心 Handler 容器。"""
        from ..core._core import MainWindowCore

        self._core = MainWindowCore(
            mgr=self._mgr,
            work_table=self.work_table,
            progress_callback=lambda v: self.progress_changed.emit(v),
            status_callback=lambda msg: self.status_changed.emit(msg),
            parsed_results=self._parsed_results,
            config=self._config,
            pause_event=self._pause_event,
            parent_widget=self,
            show_stage_dialog=self._show_stage_dialog,
            stage_prereq_dialog=self._stage_prereq_dialog,
            register_task=self._register_task,
            project_mark_dirty=lambda: self._project.mark_dirty(),
            suppress_dialogs=lambda: self._suppress_dialogs,
            add_table_row=self._add_table_row,
            find_row_by_seq=self._find_row_by_seq,
            clear_table=self._clear_table,
            update_button_states=self._update_button_states,
            question_dlg=self._question_dlg,
            reset_progress=self._reset_progress_bar,
            force_finish_progress=self._force_finish_progress,
            on_raw_progress=self._on_raw_progress,
            run_scan_cb=self._run_scan,
            run_query_cb=self._on_query,
            get_selected_path_cb=self._get_selected_path,
            get_scan_source_root_cb=lambda: self._scan_source_root,
            get_unrecognized_files_cb=lambda: self._unrecognized_files,
            clear_unrecognized_files_cb=lambda: self._unrecognized_files.clear(),
            set_suppress_dialogs=lambda v: setattr(self, "_suppress_dialogs", v),
            set_query_btn_enabled=lambda v: self.btn_query.setEnabled(v),
            set_download_btn_enabled=lambda v: self.btn_download.setEnabled(v),
            set_cancel_btn_enabled=lambda v: self.btn_cancel.setEnabled(v),
            set_progress_format=lambda v: self.progress_bar.setFormat(v),
            set_progress_bar_visible=lambda v: self.progress_bar.setVisible(v),
            show_auto_error_style=lambda: (
                self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; }"),
                self.progress_bar.setFormat(_("auto_run_failed")),
                self.progress_bar.setValue(100),
            ),
            project=self._project,
            add_row_from_dict_cb=self._add_row_from_dict,
            navigate_to_cb=self._navigate_to,
            get_work_state_cb=self._collect_state,
            set_unrecognized_files_cb=lambda files: setattr(self, "_unrecognized_files", files),
        )
