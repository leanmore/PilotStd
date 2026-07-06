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

import datetime
import logging
import os
import sys
import threading
from typing import Any, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon

from ... import core
from ...core.frozen import is_frozen
from ...i18n import _
from ..controllers.announce_mixin import AnnounceMixin
from ..controllers.archive_mixin import ArchiveMixin
from ..controllers.auto_run_mixin import AutoRunMixin
from ..controllers.cleanup_mixin import CleanupMixin
from ..controllers.dialog_mixin import DialogMixin
from ..controllers.download_mixin import DownloadMixin
from ..controllers.export_mixin import ExportMixin
from ..controllers.file_dialog_mixin import FileDialogMixin
from ..controllers.file_tree_mixin import FileTreeMixin
from ..controllers.persistence_mixin import PersistenceMixin
from ..controllers.project_mixin import ProjectMixin
from ..controllers.query import QueryMixin
from ..controllers.scan_mixin import ScanMixin
from ..controllers.table_helper_mixin import TableHelperMixin
from ..controllers.theme_mixin import ThemeMixin
from ..table_mixin import TableMixin
from ._actions import ActionsMixin
from ._ui_setup import UISetupMixin

logger = logging.getLogger("pilotstd.ui")


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
    # 三期提取 (2)
    UISetupMixin,
    ActionsMixin,
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
        self._paused: bool = False  # 暂停状态（须在 _setup_log_handler 之前初始化）
        self._pause_event = threading.Event()  # 暂停事件，供 Worker 检查
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
        logger.info("进度条: %d%%", value)
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


def run() -> None:
    """启动 GUI 应用。"""
    from ...core.logger import LoggerManager

    LoggerManager(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Qt 消息处理器：捕获 Qt C++ 层致命/严重错误 → crash_log.txt ──
    from PyQt6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler

    _qt_fatal_seen = False

    def _qt_message_handler(msg_type: QtMsgType, ctx: QMessageLogContext, msg: str) -> None:
        nonlocal _qt_fatal_seen
        level_map = {
            QtMsgType.QtDebugMsg: "DEBUG",
            QtMsgType.QtInfoMsg: "INFO",
            QtMsgType.QtWarningMsg: "WARNING",
            QtMsgType.QtCriticalMsg: "CRITICAL",
            QtMsgType.QtFatalMsg: "FATAL",
        }
        level = level_map.get(msg_type, "UNKNOWN")
        line = f"[Qt {level}] {msg}  (file={ctx.file}, line={ctx.line}, func={ctx.function})\n"
        if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            _qt_fatal_seen = True
            _crash_log = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "crash_log.txt")
            try:
                with open(_crash_log, "a", encoding="utf-8") as f:
                    f.write(f"\n{'=' * 60}\nQT {level} [{datetime.datetime.now().isoformat()}]\n{line}")
            except Exception:
                pass
        # 仍输出到 stderr 以便控制台可见
        if msg_type in (
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
            QtMsgType.QtWarningMsg,
        ):
            print(line, file=sys.stderr, flush=True)

    qInstallMessageHandler(_qt_message_handler)

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
    window._ui_translatable = True  # 初次构建完成，后续语言切换时允许 _retranslate_ui
    window.show()
    QTimer.singleShot(50, window._init_manager)  # 窗口显示后 50ms 后台初始化后端
    QTimer.singleShot(100, window.show_welcome_if_needed)
    sys.exit(app.exec())
