# pilotstd/ui/main_window.py
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

import atexit
import logging
import os
import signal
import sys
import threading
from typing import Any, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from .. import core
from ..core.frozen import is_frozen
from ..i18n import _
from ..models import ParsedStdInfo
from .controllers.announce_mixin import AnnounceMixin
from .controllers.archive_mixin import ArchiveMixin
from .controllers.auto_run_mixin import AutoRunMixin
from .controllers.cleanup_mixin import CleanupMixin
from .controllers.dialog_mixin import DialogMixin
from .controllers.download_mixin import DownloadMixin
from .controllers.export_mixin import ExportMixin
from .controllers.file_dialog_mixin import FileDialogMixin
from .controllers.file_tree_mixin import FileTreeMixin
from .controllers.persistence_mixin import PersistenceMixin
from .controllers.project_mixin import ProjectMixin
from .controllers.query_mixin import QueryMixin
from .controllers.scan_mixin import ScanMixin
from .controllers.table_helper_mixin import TableHelperMixin
from .controllers.theme_mixin import ThemeMixin

# 重型模块由 StandardManager 内部延迟初始化，GUI 直接调用 self._mgr 公共 API
from .table_mixin import WORK_COLUMN_KEYS, WORK_COLUMNS, TableMixin

logger = logging.getLogger("pilotstd.ui")

from .dialogs import ConfigPageDialog  # noqa: E402
from .workers import (  # noqa: E402
    LogHandler,
    RowUpdate,
)


class MainWindow(
    QMainWindow,
    # 一期提取 (4)
    TableMixin,
    ScanMixin,
    ArchiveMixin,
    DownloadMixin,
    QueryMixin,
    # 二期提取 (11)
    TableHelperMixin,
    FileTreeMixin,
    ExportMixin,
    CleanupMixin,
    AutoRunMixin,
    PersistenceMixin,
    AnnounceMixin,
    ProjectMixin,
    FileDialogMixin,
    DialogMixin,
    ThemeMixin,
):
    # 信号：供外部模块更新进度
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    query_result_ready = pyqtSignal(int, object)

    def __init__(self, config: "core.ConfigManager", project: "core.ProjectManager") -> None:
        super().__init__()
        self._config = config
        self._project = project
        self._current_project_path: Optional[str] = None

        self.setWindowTitle("PilotStd — 标准文件管理工具")
        self._apply_icon()
        self.setMinimumSize(1000, 550)
        self.resize(1000, 550)
        self._restore_window_geometry()
        self._menu_selected_path: str = ""  # 文件菜单选择的路径（独立于文件树）
        self._suppress_dialogs: bool = False  # 自动运行时抑制中间弹窗

        # Qt 翻译器须在控件创建前安装，否则内置右键菜单无法翻译
        self._load_qt_translator()

        self._setup_menu()
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
    # 菜单栏
    # ================================================================

    def _setup_tray(self) -> None:
        """系统托盘：最小化到托盘，双击恢复。"""
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self.windowIcon())
        self._tray.setToolTip("PilotStd")
        tray_menu = QMenu()
        tray_menu.addAction(_("tray_show"), self._restore_from_tray)
        tray_menu.addSeparator()
        tray_menu.addAction(_("exit"), self._quit_app)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()
        from ..core.notify import NotifyService

        NotifyService.init(self._tray)

    def _on_tray_activated(self, reason: Any) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()

    def _quit_app(self) -> None:
        try:
            self._db.backup()
            logger.info("数据库已备份")
        except Exception:
            logger.debug("数据库备份跳过（DB未初始化或已关闭）")
        self._tray.hide()
        app = QApplication.instance()
        assert app is not None, "QApplication 未初始化"
        app.quit()

    def changeEvent(self, event: Any) -> None:
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

    def closeEvent(self, event: Any) -> None:
        """关闭窗口时保存状态并退出。"""
        self._save_window_geometry()
        self._save_splitter_sizes()
        self._save_sort_state()
        self._save_column_widths()
        self._quit_app()
        event.accept()

    def _setup_menu(self) -> None:
        """构建菜单栏：文件 | 工具 | 设置 | 帮助。

        所有菜单项的文本通过 _() 国际化，在 _retranslate_ui 中统一刷新。
        子菜单（如"导出工作表"）使用 addMenu 创建级联菜单。
        """
        mb = self.menuBar()
        assert mb is not None, "menuBar() 不应为 None"

        # ── 文件 ──
        file_menu = mb.addMenu(_("file"))

        a = file_menu.addAction(_("open_file"), self._on_open_file)
        a.setToolTip("选择单个标准文件并导入项目")
        a = file_menu.addAction(_("open_folder"), self._on_open_folder)
        a.setToolTip("选择文件夹（含子文件夹）并导入项目")
        file_menu.addSeparator()

        save_result_menu = file_menu.addMenu(_("export_sheet"))
        save_result_menu.setToolTip("将工作区表格导出为文件")
        save_result_menu.addAction(_("export_txt"), lambda: self._on_save_result("txt"))
        save_result_menu.addAction(_("export_csv"), lambda: self._on_save_result("csv"))

        file_menu.addSeparator()
        a = file_menu.addAction(_("export_file_list"), self._on_export_file_list)
        a.setToolTip("将选中文件夹内所有文件名导出为列表（可选是否含完整路径）")
        a = file_menu.addAction(_("export_folder_tree"), self._on_export_folder_tree)
        a.setToolTip("将选中文件夹的目录树形结构导出为文本")
        file_menu.addSeparator()
        a = file_menu.addAction(_("save_query_project"), self._on_save_query_project)
        a.setToolTip("将当前查询列表保存为 .pilotstd 项目文件，便于下次恢复")
        a = file_menu.addAction(_("save_download_project"), self._on_save_download_project)
        a.setToolTip("将当前下载队列保存为 .pilotstd 项目文件，便于下次恢复")
        a = file_menu.addAction(_("import_download"), self._on_import_download)
        a.setToolTip("从文件导入标准号列表并直接下载，无需先查询")
        file_menu.addSeparator()
        a = file_menu.addAction(_("open_project"), self._on_open_project)
        a.setToolTip("从 .pilotstd 项目文件恢复之前保存的工作状态")
        file_menu.addSeparator()
        a = file_menu.addAction(_("exit"), self.close)
        a.setToolTip("退出 PilotStd（未保存的工作状态将自动保存）")

        # ── 工具 ──
        tool_menu = mb.addMenu(_("tools"))

        rule_action = tool_menu.addAction(_("query_rules"), self._on_rule_query)
        rule_action.setToolTip("管理查询/下载网站适配规则，支持 JSON 导入导出")

        tool_menu.addAction(_("task_center"), self._on_task_center)
        tool_menu.addSeparator()
        tool_menu.addAction(_("cleanup_empty_dirs"), self._on_cleanup_empty_dirs)
        tool_menu.addAction(_("collect_unrecognized"), self._on_collect_unrecognized)
        tool_menu.addSeparator()
        tool_menu.addAction(_("export_diag"), self._on_export_diag)
        tool_menu.addSeparator()
        tool_menu.addAction(_("pending_query"), self._on_pending_query)

        # ── 设置 ──
        settings_menu = mb.addMenu(_("settings"))
        settings_menu.addAction(_("preferences"), self._on_settings)

        # ── 帮助 ──
        help_menu = mb.addMenu(_("help"))
        help_menu.addAction(_("check_update"), self._on_check_update)
        help_menu.addAction(_("about"), self._on_about)

    # ================================================================
    # 工具栏
    # ================================================================

    def _setup_toolbar(self) -> None:
        """构建工具栏：导入 | 查询 | 下载 | 规范化 | 归档 | 一键处理 | 暂停 | 进度条。

        按钮使用 QPushButton + QStyle 标准图标，文本由 _retranslate_ui 国际化。
        """
        self.toolbar = QToolBar(_("toolbar_main"))
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        style = self.style()
        assert style is not None, "style() 不应为 None"

        self.btn_select = QPushButton("导入")
        self.btn_select.setIcon(style.standardIcon(style.StandardPixmap.SP_DirOpenIcon))
        self.btn_select.setToolTip("导入文件夹到项目中")
        self.btn_select.clicked.connect(self._on_select)
        self.toolbar.addWidget(self.btn_select)

        self.btn_query = QPushButton("查询")
        self.btn_query.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogContentsView))
        self.btn_query.setToolTip("对扫描后的标准号在网站上查询有效性，获取标准状态")
        self.btn_query.clicked.connect(self._on_query)
        self.toolbar.addWidget(self.btn_query)

        self.btn_download = QPushButton("下载")
        self.btn_download.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowDown))
        self.btn_download.setToolTip("对已有新版本的标准进行下载")
        self.btn_download.clicked.connect(self._on_download)
        self.toolbar.addWidget(self.btn_download)

        self.btn_normalize = QPushButton("规范化")
        self.btn_normalize.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogDetailedView))
        self.btn_normalize.setToolTip("对扫描结果生成规范标准文件名")
        self.btn_normalize.clicked.connect(self._on_normalize)
        self.toolbar.addWidget(self.btn_normalize)

        self.btn_save = QPushButton("归档")
        self.btn_save.setIcon(style.standardIcon(style.StandardPixmap.SP_DriveFDIcon))
        self.btn_save.setToolTip("将文件以规范名称保存到设定文件夹")
        self.btn_save.clicked.connect(self._on_save_to_folder)
        self.toolbar.addWidget(self.btn_save)

        self.btn_auto = QPushButton("一键处理")
        self.btn_auto.setIcon(style.standardIcon(style.StandardPixmap.SP_MediaPlay))
        self.btn_auto.setToolTip("自动依次执行 扫描→查询→下载→规范化→保存 全流程")
        self.btn_auto.clicked.connect(self._on_auto_run)
        self.toolbar.addWidget(self.btn_auto)

        self.btn_announce = QPushButton("公告检查")
        self.btn_announce.setIcon(style.standardIcon(style.StandardPixmap.SP_MessageBoxWarning))
        self.btn_announce.setToolTip("抓取国家标准/行业标准/地方标准公告，检测本地标准变更")
        self.btn_announce.clicked.connect(self._on_check_announcements)
        self.toolbar.addWidget(self.btn_announce)

        self._paused = False
        self._pause_event = threading.Event()  # 跨线程暂停信号，worker 循环中检查
        self._pause_event.set()  # 初始为"继续"状态，pause 时 clear，resume 时 set
        self._current_task: Optional[str] = None  # 当前正在执行的任务类型: scan/query/download/normalize/archive
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setIcon(style.standardIcon(style.StandardPixmap.SP_MediaPause))
        self.btn_pause.setToolTip("暂停/继续当前操作")
        self.btn_pause.clicked.connect(self._on_pause_toggle)
        self.toolbar.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setIcon(style.standardIcon(style.StandardPixmap.SP_DialogCancelButton))
        self.btn_cancel.setToolTip("停止当前操作并取消后续任务")
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_cancel.setEnabled(False)  # 初始无任务，置灰
        self.toolbar.addWidget(self.btn_cancel)

        self.toolbar.addSeparator()

    # ================================================================
    # 中央区域（左右分栏）
    # ================================================================

    def _setup_central(self) -> None:
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── 左侧：文件浏览（Win11 风格）──
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("文件导航")
        self.file_tree.setColumnCount(1)
        self.file_tree.setAnimated(True)
        self.file_tree.itemExpanded.connect(self._on_tree_item_expanded)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._on_file_tree_context_menu)
        self._populate_quick_access()

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.file_tree)

        # ── 右侧：工作区 + 日志 ──
        self._right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.work_table = QTableWidget()
        self.work_table.setColumnCount(len(WORK_COLUMNS))
        self.work_table.setHorizontalHeaderLabels([_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS))])
        # 列宽：默认值 + 最小值，标准名称(3)为Stretch吸收剩余空间，可手动拖拽不得小于最小值
        header = self.work_table.horizontalHeader()
        for c in range(len(WORK_COLUMNS)):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        # (默认宽度, 最小宽度) px
        self._col_specs: dict[int, tuple[int, int]] = {
            0: (34, 34),  # 序号
            1: (54, 54),  # 工作状态
            2: (93, 93),  # 标准编号
            3: (241, 241),  # 标准名称
            4: (54, 54),  # 生效状态
            5: (93, 93),  # 替代标准
            6: (60, 60),  # 发布日期
            7: (60, 60),  # 实施日期
            8: (65, 65),  # 发布部门
            9: (34, 34),  # 采标
        }
        self.work_table.horizontalHeader().setMinimumSectionSize(30)
        for c, (w, mn) in self._col_specs.items():
            self.work_table.setColumnWidth(c, w)
        header.sectionResized.connect(self._enforce_min_column_width)
        # 表头右键菜单：列显隐切换
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)
        self._load_column_visibility()
        self._restore_column_widths()
        self._restore_sort_state()

        self.work_table.setAlternatingRowColors(True)
        self.work_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.work_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.work_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.work_table.setSortingEnabled(True)
        self.work_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.work_table.customContextMenuRequested.connect(self._on_work_table_context_menu)
        # Ctrl+C 复制选中单元格
        self.work_table.keyPressEvent = self._table_key_press_event
        self._right_splitter.addWidget(self.work_table)

        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 10, 0)

        # 工作日志标题 + 进度条同行
        log_header = QHBoxLayout()
        log_label = QLabel(_("work_log"))
        self._log_label = log_label
        log_label.setStyleSheet("font-weight: bold; padding: 2px 4px;")
        log_header.addWidget(log_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        log_header.addWidget(self.progress_bar, 1)
        log_layout.addLayout(log_header)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(_("log_placeholder"))
        log_layout.addWidget(self.log_view)
        self._right_splitter.addWidget(log_widget)

        self._right_splitter.setSizes([500, 200])
        self._restore_splitter_sizes()

        self._main_splitter.addWidget(left_widget)
        self._main_splitter.addWidget(self._right_splitter)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([200, 700])
        self.setCentralWidget(self._main_splitter)

    # ================================================================
    # 状态栏 + 日志桥接
    # ================================================================

    def _setup_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("font-size: 10pt; color: #dcdcdc;")
        self.status_bar.showMessage(_("ready"))
        self.setStatusBar(self.status_bar)

    def _setup_log_handler(self) -> None:
        handler = LogHandler(self.log_view)
        # 注意：不要在此处调用 handler.setLevel()，LogHandler 在 __init__ 中
        # 已固定为 logging.INFO。外部覆盖为 DEBUG 会导致日志信号洪水 → c0000409 崩溃。
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)  # root logger 保持 DEBUG 供文件 handler 使用
        self._log_handler = handler
        self._apply_language()
        logger.info("PilotStd 启动完成")

    # ================================================================
    # Worker 管理
    # ================================================================

    # ── 驱动器公开方法 ──────────────────────────────────────

    def run_auto(self, source_dir: str) -> None:
        """供压力测试驱动器调用：启动统一 AutoWorker，异步返回。"""
        self._start_auto_pipeline(source_dir)

    def get_pipeline_stats(self) -> dict[str, Any]:
        """供驱动器取交叉对比数据。需在 run_auto 全部 worker 完成后调用。"""
        if not self._mgr_ready:
            return {}
        dl = self._mgr.get_stage_queue("download")
        ex = self._mgr.get_stage_queue("expire")
        pe = self._mgr.get_stage_queue("pending")
        # 精确匹配计数
        exact = (
            sum(1 for p in self._parsed_results if getattr(p, "match_status", "") == "exact")
            if self._parsed_results
            else 0
        )
        return {
            "scan_count": len(self._parsed_results) if self._parsed_results else 0,
            "query_download": len(dl),
            "query_expire": len(ex),
            "query_pending": len(pe),
            "query_exact": exact,
            "query_total": len(dl) + len(ex) + len(pe),
        }

    # ── Worker 管理 ──────────────────────────────────────────

    def _stop_workers(self) -> None:
        for attr in (
            "_query_worker",
            "_download_worker",
            "_scan_worker",
            "_normalize_worker",
            "_archive_worker",
            "_ann_worker",
            "_auto_worker",
        ):
            try:
                w = getattr(self, attr, None)
                if w is not None and w.isRunning():
                    w.stop()
                    w.quit()
                    w.wait(5000)
            except RuntimeError:
                pass

    def _on_cancel(self) -> None:
        """取消按钮：停止所有后台 Worker，恢复 UI 状态。"""
        self._stop_workers()
        # 恢复暂停状态
        self._paused = False
        self._pause_event.set()
        self.btn_pause.setText("暂停")
        s = self.style()
        assert s is not None, "style() 不应为 None"
        self.btn_pause.setIcon(s.standardIcon(s.StandardPixmap.SP_MediaPause))
        # 恢复按钮
        self.btn_query.setEnabled(True)
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._current_task = None
        self._update_button_states()
        self.status_changed.emit("操作已取消")

    # ── 工作表阶段切换 ───────────────────────────────────

    def _switch_to_stage(self, stage: str) -> None:
        """清空 work_table，从 Manager.get_stage_queue(stage) 取数据填充。
        stage: 'scan' | 'all' | 'download' | 'pending' | 'archive_ready'
        """
        if not self._mgr_ready:
            return
        items = self._mgr.get_stage_queue(stage)
        self._clear_table()
        total = len(items)
        for i, parsed in enumerate(items):
            self._add_table_row(
                RowUpdate(
                    seq=i + 1,
                    parsed=parsed,
                    work_status=parsed.stage_status,
                    total=total,
                )
            )
        self._update_button_states()

    def _update_button_states(self) -> None:
        """根据当前数据状态动态启用/禁用工具栏按钮。"""
        if not self._mgr_ready:
            return
        has_results = bool(self._parsed_results)
        has_download = bool(self._mgr.get_stage_queue("download"))
        has_archive = bool(self._mgr.get_stage_queue("all"))

        self.btn_query.setEnabled(has_results)
        self.btn_download.setEnabled(has_download)
        self.btn_normalize.setEnabled(has_archive)
        self.btn_save.setEnabled(has_archive)
        self.btn_cancel.setEnabled(False)  # 无任务时置灰

    # ================================================================
    # 自动保存
    # ================================================================

    def _setup_auto_save(self) -> None:
        app = QApplication.instance()
        assert app is not None, "QApplication 未初始化"
        app.aboutToQuit.connect(self._on_auto_save)
        atexit.register(self._on_atexit_save)
        try:
            signal.signal(signal.SIGTERM, lambda *a: self._on_auto_save())
        except (ValueError, OSError):
            pass

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
            # 保留未识别文件列表，使得重启后"工具→未识别文件处理"仍可用
            "unrecognized_files": list(getattr(self, "_unrecognized_files", [])),
        }

    # ================================================================
    # 信号回调
    # ================================================================

    def _on_pause_toggle(self) -> None:
        self._paused = not self._paused
        s = self.style()
        assert s is not None, "style() 不应为 None"
        if self._paused:
            self.btn_pause.setText(_("toolbar_continue"))
            self.btn_pause.setIcon(s.standardIcon(s.StandardPixmap.SP_MediaPlay))
            self.status_changed.emit(_("paused"))
            self._pause_event.clear()  # 清除 event → 所有 worker 在 wait() 处阻塞
        else:
            self.btn_pause.setText(_("toolbar_pause"))
            self.btn_pause.setIcon(s.standardIcon(s.StandardPixmap.SP_MediaPause))
            self.status_changed.emit(_("resumed"))
            self._pause_event.set()  # 设置 event → 所有 worker 的 wait() 返回，继续执行

    def _check_pause(self) -> None:
        """轮询等待暂停解除。使用 QApplication.processEvents 处理当前队列事件，
        不递归处理新事件（避免 QEventLoop 的栈溢出），同时允许用户点击"继续"。"""
        import time as _time

        while self._paused:
            QApplication.processEvents()
            _time.sleep(0.05)

    def _on_progress(self, value: int) -> None:
        logger.info("进度条: %d%%", value)
        self.progress_bar.setValue(value)

    def _on_status(self, msg: str) -> None:
        self.status_bar.showMessage(msg)
        logger.info(msg)

    def _setup_scanner(self) -> None:
        self._parsed_results: list[ParsedStdInfo] = []
        self._unrecognized_files: list[str] = []  # 扫描中无法识别的文件路径
        self._scan_source_root: str = ""  # 最近一次扫描的源根目录

    # ================================================================
    # 菜单动作（共享辅助）
    # ================================================================

    def _get_selected_path(self) -> str:
        """获取当前工作路径：优先文件树选择，其次文件菜单选择的路径。"""
        items = self.file_tree.selectedItems()
        if items:
            path = items[0].data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.exists(str(path)):
                return str(path)
        return self._menu_selected_path

    # ── 规则/任务/设置 ──────────────────────────────────────

    def _on_rule_query(self) -> None:
        from .pages.rules_page import RulesPage  # 延迟导入

        dlg = ConfigPageDialog(
            RulesPage(self._config),
            "网站规则配置（查询/下载）",
            self,  # type: ignore[arg-type]
        )
        dlg.exec()

    def _on_rule_download(self) -> None:
        self._on_rule_query()

    def _on_task_center(self) -> None:
        if not self._mgr_ready:
            return
        from .pages.task_page import TaskCenterDialog  # 延迟导入

        dlg = TaskCenterDialog(self._mgr.task_queue, self)  # type: ignore[arg-type]
        dlg.exec()

    def _on_settings(self) -> None:
        from .pages.settings_page import SettingsDialog  # 延迟导入

        dlg = SettingsDialog(self._config, self)  # type: ignore[arg-type]
        dlg.exec()
        self._apply_language()
        self._apply_theme()
        self._apply_icon()
        self.status_changed.emit("设置已更新")

    # ================================================================
    # 关于 / 更新
    # ================================================================

    def _on_check_update(self) -> None:
        """半自动升级：检查 GitHub Release → 下载 → 写 update.bat → 提示重启。"""
        import time as _time

        from pilotstd import __version__
        from pilotstd.core.updater import (
            check_latest_version,
            download_update,
            extract_sha256_from_body,
            generate_update_script,
            is_newer_version,
        )

        current = f"v{__version__}"

        # 24h 内不重复检查，避免触发 GitHub API 限流（60次/h 无 Token）
        last_check = self._config.get("appearance.last_update_check", 0)
        if isinstance(last_check, (int, float)) and _time.time() - last_check < 86400:
            QMessageBox.information(
                self,  # type: ignore[arg-type]
                _("title_no_update"),
                _("update_already_latest").format(current=current),
            )
            return

        self._config.set("appearance.last_update_check", _time.time())
        self._config.save()
        self.status_changed.emit(_("checking_update"))
        try:
            release = check_latest_version()
            if not release:
                raise RuntimeError("无法获取最新版本信息")

            latest = release["tag_name"]

            if not is_newer_version(latest, current):
                QMessageBox.information(
                    self,  # type: ignore[arg-type]
                    _("title_no_update"),
                    _("update_already_latest").format(current=current),
                )
                return

            body = release["body"][:500]
            reply = QMessageBox.question(
                self,  # type: ignore[arg-type]
                _("title_update_found"),
                _("update_new_version_msg").format(current=current, latest=latest, body=body),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # 源码运行模式不自动下载，引导手动 git pull
            if not getattr(sys, "frozen", False):
                import webbrowser

                webbrowser.open("https://github.com/leanmore/PilotStd/releases/latest")
                return

            download_url = release["download_url"]
            filename = release["filename"]
            self.status_changed.emit(_("update_downloading").format(filename=filename))

            dl_path = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), filename)
            sha256_expected = extract_sha256_from_body(release["body"])

            # 在后台下载（含完整性校验）
            result: dict[str, Any] = {"ok": False, "error": ""}

            def _download() -> None:
                try:
                    ok = download_update(download_url, dl_path, sha256_expected)
                    if ok:
                        result["ok"] = True
                    else:
                        result["error"] = "下载或校验失败"
                except Exception as e:
                    result["error"] = str(e)

            t = threading.Thread(target=_download, daemon=True)
            t.start()
            t.join(timeout=300)
            if not result["ok"]:
                raise RuntimeError(result["error"] or "下载超时")

            exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
            # 写入权限检查（Program Files 等系统目录可能无写入权限）
            if not os.access(exe_dir, os.W_OK):
                raise PermissionError(f"无法写入 {exe_dir}\n请以管理员身份运行，或将程序移至用户目录")
            bat_path = generate_update_script(dl_path, exe_dir)

            import subprocess

            reply = QMessageBox.question(
                self,  # type: ignore[arg-type]
                _("update_restart_title"),
                _("update_download_ready"),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Ok:
                subprocess.Popen(["cmd.exe", "/c", bat_path])
                QApplication.quit()

        except Exception as e:
            logger.warning("检查更新失败: %s", e)
            QMessageBox.information(
                self,  # type: ignore[arg-type]
                _("title_no_update"),
                _("update_connection_failed").format(current=current),
            )

    def _on_about(self) -> None:
        from pilotstd import __version__

        QMessageBox.about(self, _("about"), _("about_text").format(version=__version__))  # type: ignore[arg-type]

    # ================================================================
    # 欢迎页
    # ================================================================

    def show_welcome_if_needed(self) -> None:
        skip = self._config.get("appearance.skip_welcome", False)
        if skip:
            return
        from .welcome_dialog import WelcomeDialog  # 延迟导入

        dlg = WelcomeDialog(self)  # type: ignore[arg-type]
        dlg.exec()
        if dlg.should_skip():
            self._config.set("appearance.skip_welcome", True)
            self._config.save()

    # ================================================================
    # 延迟初始化
    # ================================================================

    def _init_manager(self) -> None:
        """延迟初始化 StandardManager——避免阻塞窗口显示。

        窗口先显示（工具栏灰色），后台加载所有子系统（DB/适配器/引擎/
        服务），完成后工具栏亮起。将 400-1200ms 的重量级初始化移出
        启动关键路径，用户从双击到看到窗口从 ~2s 缩短到 ~1s。

        可通过两种方式触发：
          1. QTimer 延迟调用（run() 中 window.show() 后 50ms）
          2. _mgr property 首次访问自动调用（向后兼容测试夹具）
        二次调用由 _mgr_ready 守卫防止重复初始化。
        """
        if self._mgr_ready:
            return  # 已初始化（property 懒加载 + QTimer 竞态保护）
        from ..manager import StandardManager

        mgr = StandardManager(config=self._config)
        self._mgr = mgr  # 必须先设 backing field，避免下游 _mgr 访问触发递归
        self._mgr_ready = True
        self._set_toolbar_enabled(True)
        self._apply_announce_cache_mode()
        self.status_bar.showMessage(_("ready"), 2000)
        # 后端就绪后执行启动检查任务（从 run() 移入，确保在后端就绪后触发）
        self._check_download_queue()
        self._check_pending_lookup()
        # 增量文件监控（按需启动，需安装 watchdog）
        if self._config.get("watchdog.enabled", False):
            mgr.start_watching()

    def _set_toolbar_enabled(self, enabled: bool) -> None:
        """统一控制工具栏按钮状态。管理器未就绪时禁用所有操作按钮。"""
        self.btn_select.setEnabled(enabled)
        self.btn_query.setEnabled(enabled)
        self.btn_download.setEnabled(enabled)
        self.btn_normalize.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        self.btn_auto.setEnabled(enabled)
        self.btn_announce.setEnabled(enabled)
        self.btn_pause.setEnabled(enabled)
        # btn_cancel 始终由任务状态控制（_on_cancel / worker 生命周期），不在此处改动

    def _apply_announce_cache_mode(self, enabled: Optional[bool] = None) -> None:
        """根据配置控制公告检查按钮启用/禁用状态。
        Web 端公告缓存开启时禁用本地公告检查，避免双数据源混淆。
        """
        if enabled is None:
            enabled = self._config.get("query.use_announcement_cache", False)
        self.btn_announce.setEnabled(not enabled)


def run() -> None:
    """启动 GUI 应用。"""
    from ..core.logger import LoggerManager

    LoggerManager(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    cfg = core.ConfigManager()
    prj = core.ProjectManager()

    # exe 模式下预创建下载目录
    if is_frozen():
        import os as _os

        dl_dir = _os.path.join(_os.path.dirname(sys.executable), "downloads")
        _os.makedirs(dl_dir, exist_ok=True)

    window = MainWindow(cfg, prj)
    window._apply_theme()
    window._apply_icon()
    window.show()
    QTimer.singleShot(50, window._init_manager)  # 窗口显示后 50ms 后台初始化后端
    QTimer.singleShot(100, window.show_welcome_if_needed)
    # _check_download_queue / _check_pending_lookup 已移入 _init_manager
    # 确保在后端就绪后才触发（而非固定时间点可能早于 init 完成）
    sys.exit(app.exec())
