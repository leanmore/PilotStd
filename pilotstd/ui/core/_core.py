# pilotstd/ui/core/_core.py
"""MainWindowCore — UI 核心容器，组合所有 Handler，替代多重继承 Mixin。

查询子系统初始化已提取至 _core_init_query.py，适配器类已提取至 _core_adapters.py。
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...core.config import ConfigManager

from ...core.config import get_library_root
from ._core_init_query import _CoreInitQueryMixin
from .handlers._announce import AnnounceUIHandler
from .handlers._archive import ArchiveUIHandler
from .handlers._auto import AutoUIHandler
from .handlers._cleanup import CleanupHandler
from .handlers._download import DownloadUIHandler
from .handlers._persistence import PersistenceHandler
from .handlers._project import ProjectHandler
from .handlers._scan import ScanUIHandler


class MainWindowCore(_CoreInitQueryMixin):
    """UI 核心容器，持有所有 UI Handler 实例，通过组合模式替代 Mixin。

    查询初始化由 _CoreInitQueryMixin 提供。
    """

    def __init__(
        self,
        mgr: Any,
        work_table: Any,
        progress_callback: Any,
        status_callback: Any,
        parsed_results: list[Any],
        config: ConfigManager,
        pause_event: threading.Event,
        parent_widget: Any,
        show_stage_dialog: Any = None,
        stage_prereq_dialog: Any = None,
        register_task: Any = None,
        project_mark_dirty: Any = None,
        suppress_dialogs: Any = None,
        add_table_row: Any = None,
        find_row_by_seq: Any = None,
        clear_table: Any = None,
        update_button_states: Any = None,
        stop_workers_cb: Any = None,
        on_auto_save_cb: Any = None,
        question_dlg: Any = None,
        reset_progress: Any = None,
        force_finish_progress: Any = None,
        on_raw_progress: Any = None,
        run_scan_cb: Any = None,
        run_query_cb: Any = None,
        get_selected_path_cb: Any = None,
        get_scan_source_root_cb: Any = None,
        get_unrecognized_files_cb: Callable[[], list[str]] | None = None,
        clear_unrecognized_files_cb: Callable[[], None] | None = None,
        set_suppress_dialogs: Any = None,
        set_query_btn_enabled: Any = None,
        set_download_btn_enabled: Any = None,
        set_cancel_btn_enabled: Any = None,
        set_progress_format: Any = None,
        set_progress_bar_visible: Any = None,
        show_auto_error_style: Any = None,
        get_parsed_results_cb: Any = None,
        get_work_table_cb: Any = None,
        get_log_view_cb: Any = None,
        project: Any = None,
        add_row_from_dict_cb: Callable[[dict], None] | None = None,
        navigate_to_cb: Callable[[str], None] | None = None,
        get_work_state_cb: Callable[[], dict] | None = None,
        set_unrecognized_files_cb: Callable[[list[str]], None] | None = None,
    ) -> None:
        self._mgr, self._config, self._pause_event = mgr, config, pause_event
        self._parent, self._work_table = parent_widget, work_table
        # 共享解析结果列表（所有 Handler 共享同一引用）
        self._parsed_results, self._status_callback = parsed_results, status_callback
        # UI 交互回调：进度、对话框、表格操作
        self._progress_callback, self._suppress_dialogs = progress_callback, suppress_dialogs
        self._register_task, self._project_mark_dirty = register_task, project_mark_dirty
        self._add_table_row, self._find_row_by_seq = add_table_row, find_row_by_seq
        self._clear_table, self._update_button_states = clear_table, update_button_states
        self._question_dlg, self._reset_progress = question_dlg, reset_progress
        self._force_finish_progress, self._on_raw_progress = force_finish_progress, on_raw_progress
        self._show_stage_dialog, self._stage_prereq_dialog = show_stage_dialog, stage_prereq_dialog
        # 工作流回调：扫描、查询、路径获取
        self._run_scan_cb, self._run_query_cb = run_scan_cb, run_query_cb
        self._get_selected_path_cb = get_selected_path_cb
        self._get_scan_source_root_cb = get_scan_source_root_cb
        self._get_unrecognized_files_cb = get_unrecognized_files_cb
        self._clear_unrecognized_files_cb = clear_unrecognized_files_cb
        self._set_suppress_dialogs, self._set_query_btn_enabled = set_suppress_dialogs, set_query_btn_enabled
        self._set_download_btn_enabled, self._set_cancel_btn_enabled = set_download_btn_enabled, set_cancel_btn_enabled
        # 进度条和样式控制回调
        self._set_progress_format, self._set_progress_bar_visible = set_progress_format, set_progress_bar_visible
        self._show_auto_error_style, self._get_parsed_results_cb = show_auto_error_style, get_parsed_results_cb
        # 其他引用：日志视图、项目、导航、工作状态
        self._get_work_table_cb, self._get_log_view_cb = get_work_table_cb, get_log_view_cb
        self._project, self._add_row_from_dict_cb = project, add_row_from_dict_cb
        self._navigate_to_cb, self._get_work_state_cb = navigate_to_cb, get_work_state_cb
        self._set_unrecognized_files_cb = set_unrecognized_files_cb
        self._stop_workers_cb, self._on_auto_save_cb = stop_workers_cb, on_auto_save_cb
        self._init_all_handlers()

    def _init_all_handlers(self) -> None:
        """批量初始化所有 UI Handler。"""
        self._init_scan()
        self._init_query()
        self._init_download()
        self._init_archive()
        self._init_auto()
        self._init_announce()
        self._init_cleanup()
        self._init_persistence()
        self._init_project()

    def _init_scan(self) -> None:
        """创建 ScanUIHandler 实例，注入扫描所需的回调函数和共享数据。"""
        self.scan = ScanUIHandler(
            mgr=self._mgr,
            config=self._config,
            pause_event=self._pause_event,
            parent_widget=self._parent,
            work_table=self._work_table,
            parsed_results=self._parsed_results,
            status_callback=self._status_callback,
            suppress_dialogs=self._suppress_dialogs,
            add_table_row=self._add_table_row,
            register_task=self._register_task,
            project_mark_dirty=self._project_mark_dirty,
            clear_table=self._clear_table,
            update_button_states=self._update_button_states,
            question_dlg=self._question_dlg,
            progress_callback=self._on_raw_progress,
            reset_progress=self._reset_progress,
            force_finish_progress=self._force_finish_progress,
            unrecognized_files=self._get_unrecognized_files_cb() if self._get_unrecognized_files_cb else [],
            scan_source_root=self._get_scan_source_root_cb() if self._get_scan_source_root_cb else "",
        )

    # _init_download — 下载 Handler
    def _init_download(self) -> None:
        """创建 DownloadUIHandler，注入下载所需的所有 UI 回调函数。"""
        self.download = DownloadUIHandler(
            mgr=self._mgr,
            config=self._config,
            pause_event=self._pause_event,
            parent_widget=self._parent,
            work_table=self._work_table,
            status_callback=self._status_callback,
            progress_callback=self._progress_callback,
            show_stage_dialog=self._show_stage_dialog,
            question_dlg=self._question_dlg,
            stage_prereq_dialog=self._stage_prereq_dialog,
            register_task=self._register_task,
            project_mark_dirty=self._project_mark_dirty,
            suppress_dialogs=self._suppress_dialogs,
            add_table_row=self._add_table_row,
            find_row_by_seq=self._find_row_by_seq,
        )

    # _init_archive — 归档 Handler
    def _init_archive(self) -> None:
        """创建 ArchiveUIHandler，注入归档/规范化所需的回调、表格操作和信号连接。"""
        self.archive = ArchiveUIHandler(
            mgr=self._mgr,
            config=self._config,
            pause_event=self._pause_event,
            parent_widget=self._parent,
            work_table=self._work_table,
            parsed_results=self._parsed_results,
            status_callback=self._status_callback,
            suppress_dialogs=self._suppress_dialogs,
            stage_prereq_dialog=self._stage_prereq_dialog,
            show_stage_dialog=self._show_stage_dialog,
            question_dlg=self._question_dlg,
            register_task=self._register_task,
            project_mark_dirty=self._project_mark_dirty,
            reset_progress=self._reset_progress,
            force_finish_progress=self._force_finish_progress,
            add_table_row=self._add_table_row,
            clear_table=self._clear_table,
            update_button_states=self._update_button_states,
            find_row_by_seq=self._find_row_by_seq,
            run_scan_cb=self._run_scan_cb,
            run_query_cb=self._run_query_cb,
            get_selected_path_cb=self._get_selected_path_cb,
            on_raw_progress=self._on_raw_progress,
        )

    # _init_auto — 自动管线 Handler
    def _init_auto(self) -> None:
        """创建 AutoUIHandler，注入自动管线所需的所有 Handler 引用和 UI 控制回调。"""
        self.auto = AutoUIHandler(
            mgr=self._mgr,
            config=self._config,
            pause_event=self._pause_event,
            parent_widget=self._parent,
            work_table=self._work_table,
            parsed_results=self._parsed_results,
            status_callback=self._status_callback,
            progress_callback=self._progress_callback,
            clear_table=self._clear_table,
            force_finish_progress=self._force_finish_progress,
            reset_progress=self._reset_progress,
            project_mark_dirty=self._project_mark_dirty,
            set_suppress_dialogs=self._set_suppress_dialogs,
            set_query_btn_enabled=self._set_query_btn_enabled,
            set_download_btn_enabled=self._set_download_btn_enabled,
            set_cancel_btn_enabled=self._set_cancel_btn_enabled,
            set_progress_format=self._set_progress_format,
            set_progress_bar_visible=self._set_progress_bar_visible,
            show_auto_error_style=self._show_auto_error_style,
            scan_handler=self.scan,
            query_handler=self.query,
            download_handler=self.download,
            archive_handler=self.archive,
        )

    def _init_announce(self) -> None:
        """创建 AnnounceUIHandler，注入公告检查所需的配置和管理器。"""
        self.announce = AnnounceUIHandler(
            mgr=self._mgr,
            config=self._config,
            parent_widget=self._parent,
            pause_event=self._pause_event,
        )

    def _init_cleanup(self) -> None:
        """创建 CleanupHandler，注入清理功能所需的目录路径回调和交互对话框。"""
        self.cleanup = CleanupHandler(
            config=self._config,
            status_callback=self._status_callback,
            question_dlg=self._question_dlg,
            get_library_root=lambda: get_library_root(self._config),
            get_unrecognized_files=self._get_unrecognized_files_cb or (lambda: []),
            clear_unrecognized_files=self._clear_unrecognized_files_cb or (lambda: None),
            get_scan_source_root=self._get_scan_source_root_cb or (lambda: ""),
            parent=self._parent,
        )

    def _init_persistence(self) -> None:
        self.persistence = PersistenceHandler(config=self._config)

    def _init_project(self) -> None:
        """创建 ProjectHandler，注入项目文件的保存/加载所需回调。"""
        self.project = ProjectHandler(
            config=self._config,
            project=self._project,
            status_callback=self._status_callback,
            clear_table=self._clear_table,
            add_row_from_dict=self._add_row_from_dict_cb or (lambda d: None),
            navigate_to=self._navigate_to_cb or (lambda p: None),
            get_work_state=self._get_work_state_cb or (lambda: {}),
            set_unrecognized_files=self._set_unrecognized_files_cb or (lambda f: None),
            parent=self._parent,
        )
