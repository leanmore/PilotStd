# 模块：项目//入口_/__脚本
# 窗口生命周期混入—从____脚本提取
# 系统托盘恢复、关闭退出、窗口事件、管理、自动保存

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from ...i18n import _
from ..qt_lifecycle import stop_worker_gracefully

if TYPE_CHECKING:
    # 仅类型检查期以 QMainWindow 为基类：运行时仍是纯 Mixin（不改变 MRO）
    from PyQt6.QtGui import QCloseEvent
    from PyQt6.QtWidgets import QMainWindow as _MixinBase
else:
    _MixinBase = object

logger = logging.getLogger("pilotstd.ui")


class _WindowLifecycleMixin(_MixinBase):
    """窗口生命周期方法集合（混入 MainWindow）。

    包含系统托盘交互、窗口事件处理、Worker 线程管理、状态收集与自动保存。

    架构决策：此 Mixin 不做提取/消除（白名单保留）。
    原因：Qt 框架要求 closeEvent / changeEvent 等生命周期方法
    必须通过 MRO 链分发到 QMainWindow 子类。这是 Qt 事件系统的硬约束，
    不是设计选择。强行拆分会引入无意义的转发样板。
    参见：docs/architecture/mixin-cleanup.md
    """

    # 由 MainWindow 组合提供：显式声明类型，避免 attr-defined（D-17）
    _mgr: Any
    _mgr_ready: bool
    _tray: Any
    _project: Any
    _save_window_geometry: Callable[[], None]
    _save_splitter_sizes: Callable[[], None]
    _save_sort_state: Callable[[], None]
    _save_column_widths: Callable[[], None]
    _start_auto_pipeline: Callable[[str], None]
    _table_to_list: Callable[[], list[Any]]

    # ================================================================ 分隔
    # 系统托盘
    # ================================================================ 分隔

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()

    def _quit_app(self) -> None:
        """备份数据库、关闭管理器、隐藏托盘并退出应用。"""
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

    # ================================================================ 分隔
    # 窗口事件
    # ================================================================ 分隔

    def changeEvent(self, event: QEvent | None) -> None:
        """窗口最小化时隐藏到系统托盘。"""
        if event is None:
            return
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
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

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """关闭窗口时保存状态并退出。"""
        self._save_window_geometry()
        self._save_splitter_sizes()
        self._save_sort_state()
        self._save_column_widths()
        self._stop_workers()
        self._quit_app()
        if event is not None:
            event.accept()

    # ================================================================ 分隔
    # 管理
    # ================================================================ 分隔

    def run_auto(self, source_dir: str) -> None:
        """供压力测试驱动器调用：启动统一 AutoWorker，异步返回。"""
        self._start_auto_pipeline(source_dir)

    def _stop_workers(self) -> None:
        """解除暂停并停止所有后台 Worker 线程（扫描/查询/下载/归档/公告/自动）。"""
        # 先解除暂停，防止卡在__.()中无法退出
        if hasattr(self, "_pause_event"):
            self._pause_event.set()
        if hasattr(self, "_core"):
            self._core.announce.stop_workers()
            self._core.download.stop_workers()
            self._core.scan.stop_workers()
            self._core.query.stop_workers()
            self._core.archive.stop_workers()
            self._core.auto.stop_workers()
        for attr in ("_drive_thread",):
            w = getattr(self, attr, None)
            if w is None:
                continue
            # DriveEnumerator 没有 stop()：helper 会跳过缺失的停止方法，
            # 但一定先断开 drives_ready，避免迟到信号访问已析构的文件树
            stop_worker_gracefully(w, signals=(getattr(w, "drives_ready", None),))

    # ================================================================ 分隔
    # 自动保存
    # ================================================================ 分隔

    def _on_auto_save(self) -> None:
        """退出前自动保存：停止文件监控 + 保存脏项目状态。"""
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
