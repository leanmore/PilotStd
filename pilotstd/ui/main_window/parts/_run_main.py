"""Application entry point — extracted from main_window/__init__.py for G-010 compliance."""

from __future__ import annotations

import logging
import os
import sys

from PyQt6.QtCore import QMessageLogContext, QTimer, QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication


def run() -> None:
    """启动 GUI 应用。"""
    from ...core.config import ConfigManager
    from ...core.frozen import is_frozen
    from ...core.logger import LoggerManager
    from ...core.project import ProjectManager
    from . import MainWindow

    LoggerManager(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Qt 消息处理器：捕获 Qt C++ 层致命/严重错误 → crash_log.txt ──
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
        if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg, QtMsgType.QtWarningMsg):
            print(line, file=sys.stderr, flush=True)

    qInstallMessageHandler(_qt_message_handler)

    cfg = ConfigManager()
    prj = ProjectManager()

    # exe 模式下预创建下载目录
    if is_frozen():
        dl_dir = os.path.join(os.path.dirname(sys.executable), "downloads")
        os.makedirs(dl_dir, exist_ok=True)

    window = MainWindow(cfg, prj)
    window._apply_theme()
    window._apply_icon()
    window._ui_translatable = True
    window.show()
    QTimer.singleShot(50, window._init_manager)
    QTimer.singleShot(100, window.show_welcome_if_needed)
    sys.exit(app.exec())
