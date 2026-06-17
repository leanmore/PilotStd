import logging
from pilotstd.ui.main_window import LogHandler
from PyQt6.QtWidgets import QTextEdit


def test_loghandler_filters_debug(qtbot):
    """Logger.debug 被 LogHandler.setLevel(INFO) 过滤，不进入缓冲区。"""
    widget = QTextEdit()
    qtbot.addWidget(widget)
    handler = LogHandler(widget)
    logger = logging.getLogger("test_debug_filter")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.debug("should be filtered")
    logger.removeHandler(handler)
    assert len(handler._buf) == 0, "DEBUG 消息应被 LogHandler 过滤"


def test_loghandler_passes_info(qtbot):
    """Logger.info 正常进入 LogHandler 缓冲区。"""
    widget = QTextEdit()
    qtbot.addWidget(widget)
    handler = LogHandler(widget)
    logger = logging.getLogger("test_info_pass")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("should pass")
    logger.removeHandler(handler)
    assert len(handler._buf) > 0, "INFO 消息应进入缓冲区"


def test_loghandler_passes_warning(qtbot):
    """Logger.warning（高于 INFO）正常进入缓冲区。"""
    widget = QTextEdit()
    qtbot.addWidget(widget)
    handler = LogHandler(widget)
    logger = logging.getLogger("test_warn_pass")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.warning("should pass")
    logger.removeHandler(handler)
    assert len(handler._buf) > 0, "WARNING 消息应进入缓冲区"
