# tests/gui/conftest.py
import logging
import os
import shutil
import sys
import tempfile

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PyQt6.QtWidgets import QApplication

from pilotstd import core
from pilotstd.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setStyle("Fusion")
    yield app


@pytest.fixture
def test_data_dir():
    """返回 fixtures 目录路径，包含样本标准文件名文件。"""
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def mock_main_window(qapp, qtbot, test_data_dir):
    """创建 mock 模式下的 MainWindow，查询和下载使用 mock 适配器。"""
    tmpdir = tempfile.mkdtemp(prefix="pilotstd_gui_test_")

    config_path = os.path.join(tmpdir, "config.json")
    cfg = core.ConfigManager(filepath=config_path)
    cfg.set("query.use_cache", False)
    cfg.set("storage.root_dir", os.path.join(tmpdir, "library"))
    cfg.set("appearance.skip_welcome", True)

    prj = core.ProjectManager()
    window = MainWindow(cfg, prj)

    # 注入 mock 适配器直接替换 Manager 的引擎（所有操作走 self._mgr）
    from pilotstd.core.db import Database
    from pilotstd.download.engine import DownloadEngine
    from pilotstd.download.session import SessionManager
    from pilotstd.query.cache import CacheRepository
    from pilotstd.query.engine import QueryEngine
    from tests.adapters.mock import MockQueryAdapter
    from tests.adapters.mock_download import MockDownloadAdapter

    db_path = os.path.join(tmpdir, "test.db")
    _db = Database(db_path)
    _cache = CacheRepository(_db)
    _cache.clear_all()

    window._mgr.query_engine = QueryEngine(
        adapters=[MockQueryAdapter()],
        cache=_cache,
        use_cache=False,
        rotator=None,
        quota_tracker=None,
        site_order=None,
    )
    window._mgr.download_engine = DownloadEngine(
        adapters=[MockDownloadAdapter(session=SessionManager().create_session())],
        session_manager=SessionManager(),
        save_root=os.path.join(tmpdir, "downloads"),
    )
    window._use_threaded_query = True

    window._suppress_dialogs = True
    window.show()
    qtbot.addWidget(window)
    qtbot.waitExposed(window)

    yield window

    # 先移除 LogHandler，防止 worker 线程写已销毁的 QTextEdit
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if hasattr(window, "_log_handler") and h is window._log_handler:
            root_logger.removeHandler(h)
    # 再停掉所有后台 worker 线程
    if hasattr(window, "_stop_workers"):
        window._stop_workers()
    window.close()
    window.deleteLater()
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def window(mock_main_window):
    """别名，多数测试用此 fixture。"""
    return mock_main_window


# ── 真实网络 MainWindow fixture（冷启模拟） ──


@pytest.fixture
def real_window(qapp, qtbot):
    """创建真实网络模式下的 MainWindow，用于冷启动压测。

    DB 非 mock，适配器非 mock——真实 HTTP 请求。
    _suppress_dialogs=True 阻断阶段弹窗，模拟自动点击。
    """
    import tempfile

    from pilotstd import core
    from pilotstd.ui.main_window import MainWindow

    _tmp = tempfile.mkdtemp(prefix="stress_cold_")

    config_path = os.path.join(_tmp, "config.json")
    cfg = core.ConfigManager(filepath=config_path)
    cfg.set("query.use_cache", True)
    cfg.set("storage.root_dir", os.path.join(_tmp, "library"))
    cfg.set("appearance.skip_welcome", True)
    # 公告自动更新关闭——冷启不应触发
    cfg.set("announcement.auto_check", False)

    prj = core.ProjectManager()
    win = MainWindow(cfg, prj)
    win._suppress_dialogs = True
    win.show()
    qtbot.addWidget(win)
    qtbot.waitExposed(win)

    yield win

    # 清理：先停 worker，再关窗口
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if hasattr(win, "_log_handler") and h is win._log_handler:
            root_logger.removeHandler(h)
    if hasattr(win, "_stop_workers"):
        win._stop_workers()
    win.close()
    win.deleteLater()
    if os.path.isdir(_tmp):
        shutil.rmtree(_tmp, ignore_errors=True)
