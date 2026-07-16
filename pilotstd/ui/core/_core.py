# pilotstd/ui/core/_core.py
"""MainWindowCore — UI 核心容器，组合所有 Handler，替代多重继承 Mixin。"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...core.config import ConfigManager

from ...core.config import get_library_root
from .handlers._actions import ActionsHandler
from .handlers._announce import AnnounceUIHandler
from .handlers._archive import ArchiveUIHandler
from .handlers._auto import AutoUIHandler
from .handlers._cleanup import CleanupHandler
from .handlers._download import DownloadUIHandler
from .handlers._export import ExportHandler
from .handlers._file_dialog import FileDialogHandler
from .handlers._persistence import PersistenceHandler
from .handlers._project import ProjectHandler
from .handlers._query import QueryUIHandler
from .handlers._scan import ScanUIHandler
from .handlers._theme import ThemeHandler
from .handlers._ui_setup import UISetupHandler


class MainWindowCore:
    """UI 核心容器，持有所有 UI Handler 实例，通过组合模式替代 Mixin。"""

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
        """组合所有 Handler 实例。"""
        self._mgr, self._config, self._pause_event = mgr, config, pause_event
        self._parent, self._work_table = parent_widget, work_table
        self._parsed_results, self._status_callback = parsed_results, status_callback
        print(f"[TRACE] MainWindowCore.__init__: _parsed_results id={id(self._parsed_results)}")
        self._progress_callback, self._suppress_dialogs = progress_callback, suppress_dialogs
        self._register_task, self._project_mark_dirty = register_task, project_mark_dirty
        self._add_table_row, self._find_row_by_seq = add_table_row, find_row_by_seq
        self._clear_table, self._update_button_states = clear_table, update_button_states
        self._question_dlg, self._reset_progress = question_dlg, reset_progress
        self._force_finish_progress, self._on_raw_progress = force_finish_progress, on_raw_progress
        self._show_stage_dialog, self._stage_prereq_dialog = show_stage_dialog, stage_prereq_dialog
        self._run_scan_cb, self._run_query_cb = run_scan_cb, run_query_cb
        self._get_selected_path_cb = get_selected_path_cb
        self._get_scan_source_root_cb = get_scan_source_root_cb
        self._get_unrecognized_files_cb = get_unrecognized_files_cb
        self._clear_unrecognized_files_cb = clear_unrecognized_files_cb
        self._set_suppress_dialogs, self._set_query_btn_enabled = set_suppress_dialogs, set_query_btn_enabled
        self._set_download_btn_enabled, self._set_cancel_btn_enabled = set_download_btn_enabled, set_cancel_btn_enabled
        self._set_progress_format, self._set_progress_bar_visible = set_progress_format, set_progress_bar_visible
        self._show_auto_error_style, self._get_parsed_results_cb = show_auto_error_style, get_parsed_results_cb
        self._get_work_table_cb, self._get_log_view_cb = get_work_table_cb, get_log_view_cb
        self._project, self._add_row_from_dict_cb = project, add_row_from_dict_cb
        self._navigate_to_cb, self._get_work_state_cb = navigate_to_cb, get_work_state_cb
        self._set_unrecognized_files_cb = set_unrecognized_files_cb
        self._stop_workers_cb, self._on_auto_save_cb = stop_workers_cb, on_auto_save_cb

        self._init_all_handlers()

    # ── Handler 初始化方法（每个方法创建一个 Handler 实例）──

    def _init_all_handlers(self) -> None:
        """批量初始化所有 UI Handler。"""
        self._init_scan()
        self._init_query()
        self._init_download()
        self._init_archive()
        self._init_auto()
        self._init_announce()
        self._init_file_dialog()
        self._init_export()
        self._init_cleanup()
        self._init_persistence()
        self._init_project()
        self._init_ui_setup()
        self._init_theme()
        self._init_actions()

    def _init_scan(self) -> None:
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
            unrecognized_files=self._get_unrecognized_files_cb() if self._get_unrecognized_files_cb else [],
            scan_source_root=self._get_scan_source_root_cb() if self._get_scan_source_root_cb else "",
        )

    def _init_query(self) -> None:
        # ── 适配器：将 MainWindowCore 的回调打包进协议接口 ──

        class _TableOpsAdapter:
            def __init__(self, core: MainWindowCore) -> None:
                self._c = core

            def add_table_row(self, data: dict) -> int:
                from ...workers import RowUpdate

                update = RowUpdate(
                    seq=data.get("seq", 0),
                    parsed=data.get("parsed"),
                    work_status=data.get("work_status", ""),
                    total=data.get("total", 0),
                )
                self._c._add_table_row(update)
                return 0

            def find_row_by_seq(self, seq: int) -> int:
                return self._c._find_row_by_seq(seq)

            def clear_table(self) -> None:
                self._c._clear_table()

            def get_table_as_list(self) -> list:
                return []

            def remove_selected_rows(self) -> None:
                pass

            def get_selected_path(self) -> str:
                return self._c._get_selected_path_cb() if self._c._get_selected_path_cb else ""

            def get_selected_seq(self) -> str | None:
                return None

            def get_work_table(self) -> Any:
                return self._c._work_table

        class _DialogOpsAdapter:
            def __init__(self, core: MainWindowCore) -> None:
                self._c = core

            def question_dlg(self, title: str, msg: str) -> bool:
                from PyQt6.QtWidgets import QMessageBox

                result = self._c._question_dlg(title, msg)
                return result == QMessageBox.StandardButton.Yes

            def stage_prereq_dialog(self, title: str, msg: str, task_name: str) -> str | None:
                return self._c._stage_prereq_dialog(title, msg, task_name)

            def show_stage_dialog(
                self, title: str, content: str, next_action: Any = None
            ) -> None:
                self._c._show_stage_dialog(title, content, next_action)

            def info_dlg(self, title: str, msg: str) -> None:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.information(self._c._parent, title, msg)

            def warning_dlg(self, title: str, msg: str) -> None:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(self._c._parent, title, msg)

        class _TaskOpsAdapter:
            def __init__(self, core: MainWindowCore) -> None:
                self._c = core

            def register_task(self, *args: Any, **kwargs: Any) -> str:
                self._c._register_task(*args, **kwargs)
                return ""

            def update_task_status(self, task_id: str, progress: int, msg: str = "") -> None:
                pass

            def task_completed(self, task_id: str) -> None:
                pass

            def get_task_status(self, task_id: str) -> dict | None:
                return None

        class _QueryWorkerFactoryAdapter:
            def __init__(self, core: MainWindowCore) -> None:
                from .handlers.query_worker_factory import QueryWorkerFactory

                self._c = core
                self._factory = QueryWorkerFactory(
                    core._mgr, core._pause_event, core._parent
                )

            def create_query_worker(self, parsed_list: list, callbacks: Any) -> Any:
                return self._factory.create_query_worker(parsed_list, callbacks)

            def create_pending_query_dialog(self, data: list, parent: Any) -> Any:
                from ...ui.pending_query_dialog import PendingQueryDialog

                return PendingQueryDialog(self._c._mgr, data, parent)

        deps = type(
            "QueryDeps",
            (),
            {
                "table": _TableOpsAdapter(self),
                "dialog": _DialogOpsAdapter(self),
                "task": _TaskOpsAdapter(self),
                "worker_factory": _QueryWorkerFactoryAdapter(self),
            },
        )()

        self.query = QueryUIHandler(
            deps=deps,
            config=self._config,
            mgr=self._mgr,
            parsed_results=self._parsed_results,
            run_scan_cb=self._run_scan_cb,
            status_changed=self._status_callback,
            progress_changed=self._progress_callback,
            reset_progress=self._reset_progress,
            force_finish_progress=self._force_finish_progress,
            suppress_dialogs=self._suppress_dialogs,
            project_mark_dirty=self._project_mark_dirty,
        )

    def _init_download(self) -> None:
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

    def _init_archive(self) -> None:
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

    def _init_auto(self) -> None:
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
        self.announce = AnnounceUIHandler(
            mgr=self._mgr,
            config=self._config,
            parent_widget=self._parent,
            pause_event=self._pause_event,
        )

    def _init_file_dialog(self) -> None:
        self.file_dialog = FileDialogHandler(
            config=self._config,
            status_callback=self._status_callback,
            run_scan_callback=self._run_scan_cb,
            get_selected_path_callback=self._get_selected_path_cb,
            parent=self._parent,
        )

    def _init_export(self) -> None:
        self.export = ExportHandler(
            config=self._config,
            status_callback=self._status_callback,
            get_selected_path=self._get_selected_path_cb,
            get_parsed_results=self._get_parsed_results_cb,
            get_work_table=self._get_work_table_cb,
            get_log_view=self._get_log_view_cb,
            parent=self._parent,
        )

    def _init_cleanup(self) -> None:
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

    def _init_ui_setup(self) -> None:
        self.ui_setup = UISetupHandler(
            config=self._config,
            mgr=self._mgr,
            project=self._project,
            status_callback=self._status_callback,
            progress_callback=self._progress_callback,
            on_auto_save=self._on_auto_save_cb or (lambda: None),
            parent=self._parent,
        )

    def _init_theme(self) -> None:
        self.theme = ThemeHandler(config=self._config, parent=self._parent)

    def _init_actions(self) -> None:
        self.actions = ActionsHandler(
            config=self._config,
            mgr=self._mgr,
            project=self._project,
            pause_event=self._pause_event,
            status_callback=self._status_callback,
            progress_callback=self._progress_callback,
            parsed_results=self._parsed_results,
            get_selected_path=self._get_selected_path_cb or (lambda: ""),
            clear_table=self._clear_table or (lambda: None),
            stop_workers=self._stop_workers_cb or (lambda: None),
            update_button_states=self._update_button_states or (lambda: None),
            parent=self._parent,
        )
