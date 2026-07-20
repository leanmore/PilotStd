# pilotstd/ui/core/_core.py
"""MainWindowCore — UI 核心容器，组合所有 Handler，替代多重继承 Mixin。"""
# Handler 组合模式：每个功能域一个 Handler 实例，通过 _init_* 方法创建和注入依赖

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
        # ── 核心注入：管理器、配置、暂停事件 ──
        self._mgr, self._config, self._pause_event = mgr, config, pause_event
        self._parent, self._work_table = parent_widget, work_table
        # 共享解析结果列表（所有 Handler 共享同一引用）
        self._parsed_results, self._status_callback = parsed_results, status_callback
        print(f"[TRACE] MainWindowCore.__init__: _parsed_results id={id(self._parsed_results)}")
        # ── UI 交互回调：进度、对话框、表格操作 ──
        self._progress_callback, self._suppress_dialogs = progress_callback, suppress_dialogs
        self._register_task, self._project_mark_dirty = register_task, project_mark_dirty
        self._add_table_row, self._find_row_by_seq = add_table_row, find_row_by_seq
        self._clear_table, self._update_button_states = clear_table, update_button_states
        self._question_dlg, self._reset_progress = question_dlg, reset_progress
        self._force_finish_progress, self._on_raw_progress = force_finish_progress, on_raw_progress
        self._show_stage_dialog, self._stage_prereq_dialog = show_stage_dialog, stage_prereq_dialog
        # ── 工作流回调：扫描、查询、路径获取 ──
        self._run_scan_cb, self._run_query_cb = run_scan_cb, run_query_cb
        self._get_selected_path_cb = get_selected_path_cb
        self._get_scan_source_root_cb = get_scan_source_root_cb
        self._get_unrecognized_files_cb = get_unrecognized_files_cb
        self._clear_unrecognized_files_cb = clear_unrecognized_files_cb
        # ── UI 控制回调：按钮状态、进度条、错误样式 ──
        self._set_suppress_dialogs, self._set_query_btn_enabled = set_suppress_dialogs, set_query_btn_enabled
        self._set_download_btn_enabled, self._set_cancel_btn_enabled = set_download_btn_enabled, set_cancel_btn_enabled
        self._set_progress_format, self._set_progress_bar_visible = set_progress_format, set_progress_bar_visible
        self._show_auto_error_style, self._get_parsed_results_cb = show_auto_error_style, get_parsed_results_cb
        # ── 其他引用：日志视图、项目、导航、工作状态 ──
        self._get_work_table_cb, self._get_log_view_cb = get_work_table_cb, get_log_view_cb
        self._project, self._add_row_from_dict_cb = project, add_row_from_dict_cb
        self._navigate_to_cb, self._get_work_state_cb = navigate_to_cb, get_work_state_cb
        self._set_unrecognized_files_cb = set_unrecognized_files_cb
        self._stop_workers_cb, self._on_auto_save_cb = stop_workers_cb, on_auto_save_cb
        # ── 批量初始化所有 Handler ──

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

    # _init_scan — 初始化扫描 Handler，注入扫描所需回调
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

    # _init_query — 依次初始化 UI 适配器、信号连接和状态变量
    def _init_query(self) -> None:
        """查询初始化入口：依次初始化 UI 适配器、信号连接和状态变量。"""
        self._init_query_ui()
        self._init_query_connections()
        self._init_query_state()

    def _init_query_ui(self) -> None:
        """初始化查询相关UI组件适配器"""
        # ── 适配器：将 MainWindowCore 的回调打包进协议接口 ──

        # ── TableOps 适配器 ──

        # _TableOpsAdapter — 将 MainWindowCore 回调包装进 ITableOps 协议接口
        # 用于解耦 QueryUIHandler 和 MainWindowCore 之间的表格操作

        class _TableOpsAdapter:
            """表格操作适配器：将 MainWindowCore 的回调包装进 ITableOps 协议接口。"""

            def __init__(self, core: MainWindowCore) -> None:
                self._c = core

            def add_table_row(self, data: dict) -> int:
                """添加表格行并返回行号。将 dict 转换为 RowUpdate 后委托给核心回调。"""
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
                """按序号查找行号，委托给核心回调。"""
                return self._c._find_row_by_seq(seq)

            def clear_table(self) -> None:
                """清空工作区表格。"""
                self._c._clear_table()

            def get_table_as_list(self) -> list:
                """获取表格全部数据为字典列表（当前未实现，返回空列表）。"""
                return []

            def remove_selected_rows(self) -> None:
                """移除选中行（当前为占位实现）。"""
                pass

            def get_selected_path(self) -> str:
                """获取当前在文件树中选中的路径。"""
                return self._c._get_selected_path_cb() if self._c._get_selected_path_cb else ""

            def get_selected_seq(self) -> str | None:
                """获取当前选中行的序号（当前未实现，返回 None）。"""
                return None

            def get_work_table(self) -> Any:
                """返回 QTableWidget 引用。"""
                return self._c._work_table

        # ── DialogOps 适配器 ──

        # _DialogOpsAdapter — 将 MainWindowCore 回调包装进 IDialogOps 协议接口
        class _DialogOpsAdapter:
            """对话框操作适配器：将 MainWindowCore 的回调包装进 IDialogOps 协议接口。"""

            def __init__(self, core: MainWindowCore) -> None:
                self._c = core

            def question_dlg(self, title: str, msg: str) -> bool:
                """弹出是/否确认对话框，返回用户选择（True=是）。"""
                from PyQt6.QtWidgets import QMessageBox

                result = self._c._question_dlg(title, msg)
                return result == QMessageBox.StandardButton.Yes

            def stage_prereq_dialog(self, title: str, msg: str, task_name: str) -> str | None:
                """弹出阶段前置条件对话框，返回用户选择的操作。"""
                return self._c._stage_prereq_dialog(title, msg, task_name)

            def show_stage_dialog(self, title: str, content: str, next_action: Any = None) -> None:
                """弹出阶段结果展示对话框。"""
                self._c._show_stage_dialog(title, content, next_action)

            def info_dlg(self, title: str, msg: str) -> None:
                """弹出信息提示对话框。"""
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.information(self._c._parent, title, msg)

            def warning_dlg(self, title: str, msg: str) -> None:
                """弹出警告提示对话框。"""
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(self._c._parent, title, msg)

        self._table_ops = _TableOpsAdapter(self)
        self._dialog_ops = _DialogOpsAdapter(self)

    def _init_query_connections(self) -> None:
        """连接查询相关信号：创建 TaskOpsAdapter 和 WorkerFactoryAdapter 依赖。"""
        core = self

        class _TaskOpsAdapter:
            """任务操作适配器：将 register_task 等操作包装进 ITaskOps 协议。"""

            def __init__(self, core: MainWindowCore) -> None:
                self._c = core

            def register_task(self, *args: Any, **kwargs: Any) -> str:
                """注册新任务，委托给核心回调，返回空字符串（UI 层不追踪返回值）。"""
                self._c._register_task(*args, **kwargs)
                return ""

            def update_task_status(self, task_id: str, progress: int, msg: str = "") -> None:
                """更新任务进度（当前为占位实现）。"""
                pass

            def task_completed(self, task_id: str) -> None:
                """标记任务完成（当前为占位实现）。"""
                pass

            def get_task_status(self, task_id: str) -> dict | None:
                """获取任务状态（当前未实现，返回 None）。"""
                return None

        class _QueryWorkerFactoryAdapter:
            """Worker 工厂适配器：包装 QueryWorkerFactory 和 PendingQueryDialog 创建逻辑。"""

            def __init__(self, core: MainWindowCore) -> None:
                from .handlers.query_worker_factory import QueryWorkerFactory

                self._c = core
                self._factory = QueryWorkerFactory(core._mgr, core._pause_event, core._parent)

            def create_query_worker(self, parsed_list: list, callbacks: Any) -> Any:
                """委托工厂创建查询 Worker 实例。"""
                return self._factory.create_query_worker(parsed_list, callbacks)

            def create_pending_query_dialog(self, data: list, parent: Any) -> Any:
                """创建待确认查询对话框实例。"""
                from ...ui.pending_query_dialog import PendingQueryDialog

                return PendingQueryDialog(self._c._mgr, data, parent)

        self._deps = type(
            "QueryDeps",
            (),
            {
                "table": self._table_ops,
                "dialog": self._dialog_ops,
                "task": _TaskOpsAdapter(core),
                "worker_factory": _QueryWorkerFactoryAdapter(core),
            },
        )()

    def _init_query_state(self) -> None:
        """初始化查询状态变量并创建 QueryUIHandler"""
        self.query = QueryUIHandler(
            deps=self._deps,
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

    # _init_archive — 初始化归档 Handler，注入归档规范化所需回调
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

    # _init_auto — 初始化自动流水线 Handler，注入各阶段 Handler 引用
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

    def _init_file_dialog(self) -> None:
        """创建 FileDialogHandler，注入文件选择对话框所需的配置和路径回调。"""
        self.file_dialog = FileDialogHandler(
            config=self._config,
            status_callback=self._status_callback,
            run_scan_callback=self._run_scan_cb,
            get_selected_path_callback=self._get_selected_path_cb,
            parent=self._parent,
        )

    def _init_export(self) -> None:
        """创建 ExportHandler，注入导出功能所需的懒加载回调（表格、日志视图等）。"""
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
        """创建 PersistenceHandler，用于窗口状态持久化（几何、分割器、列宽等）。"""
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

    def _init_ui_setup(self) -> None:
        """创建 UISetupHandler，注入界面布局初始化所需的配置和信号。"""
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
        """创建 ThemeHandler，用于主题/图标/语言的切换管理。"""
        self.theme = ThemeHandler(config=self._config, parent=self._parent)

    def _init_actions(self) -> None:
        """创建 ActionsHandler，注入全局操作（暂停、取消、停止 Worker）所需的回调。"""
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
