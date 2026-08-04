"""Application entry point — extracted from main_window/__init__.py for G-010 compliance."""

from __future__ import annotations

import logging
import os
import sys

from PyQt6.QtCore import QMessageLogContext, QTimer, QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication


def run() -> None:  # pragma: no cover — app.exec() 入口，单元测试不可达
    """启动 GUI 应用。"""
    from pilotstd.core.config import ConfigManager
    from pilotstd.core.frozen import is_frozen
    from pilotstd.core.logger import LoggerManager
    from pilotstd.core.project import ProjectManager

    from .. import MainWindow

    LoggerManager(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ──界面框架消息处理器：捕获界面框架++层致命/严重错误→_文本──
    _qt_fatal_seen = False

    def _qt_message_handler(msg_type: QtMsgType, ctx: QMessageLogContext, msg: str) -> None:
        """Qt 消息处理器：捕获 C++ 层致命/严重错误并写入 stderr。"""
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

    # 模式下预创建下载目录
    if is_frozen():
        dl_dir = os.path.join(os.path.dirname(sys.executable), "downloads")
        os.makedirs(dl_dir, exist_ok=True)

    window = MainWindow(cfg, prj)
    window._apply_theme()
    window._apply_icon()
    window._ui_translatable = True
    window.show()

    # 界面框架销毁前关闭，释放对的引用
    def _close_log_handlers() -> None:
        """应用退出前关闭所有 LogHandler，释放 QTextEdit 引用。"""
        from ...workers._common import LogHandler

        for h in logging.getLogger().handlers:
            if isinstance(h, LogHandler):
                h.close()

    app.aboutToQuit.connect(_close_log_handlers)

    QTimer.singleShot(50, window._init_manager)
    QTimer.singleShot(100, window.show_welcome_if_needed)
    sys.exit(app.exec())
