# tests/gui/conftest.py
"""GUI 测试基础设施。

混合弹窗处理方案：
  QFileDialog → 默认 mock patch（速度最快，PILOTSTD_USE_PYWAUTO=1 启用 pywinauto）
  QMessageBox 静态方法 → session 级 monkeypatch
  自定义 QDialog/QMessageBox 实例 → SmartDialogInterceptor 事件过滤器

调试 QFileDialog 阻塞：
  python debug_dialog_probe.py  # 终端 A
  pytest tests/gui/...          # 终端 B（触发卡死的测试）
  观察终端 A 输出定位根因。

环境变量：
  PILOTSTD_ALLOW_NETWORK=1     跳过 HTTP 阻断（压测需要）
  PILOTSTD_USE_PYWAUTO=1       启用 pywinauto 后台线程处理 QFileDialog
"""

import logging
import os
import re
import shutil
import sys
import tempfile
from unittest.mock import patch

import pytest
import responses

# 全局测试模式 — 禁止所有弹窗
os.environ["PILOTSTD_TEST_MODE"] = "1"

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PyQt6.QtWidgets import QApplication, QMessageBox

from pilotstd import core
from pilotstd.ui.main_window import MainWindow

# ── 会话级临时目录 ──────────────────────────────────────────
_TMPDIR = tempfile.mkdtemp(prefix="pilotstd_gui_mock_")
_MOCK_FILE = os.path.join(_TMPDIR, "mock_selected.file")
_MOCK_DIR = os.path.join(_TMPDIR, "mock_dir")
os.makedirs(_MOCK_DIR, exist_ok=True)
with open(_MOCK_FILE, "w") as _f:
    _f.write("mock")


# ════════════════════════════════════════════════════════════════
# 环境检测：pywinauto 可用性
# ════════════════════════════════════════════════════════════════


def _should_use_pywinauto() -> bool:
    """判断是否启用 pywinauto 处理 QFileDialog。

    本地开发环境（非 CI）且 pywinauto 已安装时默认启用。
    CI 环境（CI=true）或 PILOTSTD_USE_PYWAUTO=0 时强制禁用。
    PILOTSTD_USE_PYWAUTO=1 时强制启用。
    """
    # 用户显式控制
    env_override = os.environ.get("PILOTSTD_USE_PYWAUTO", "")
    if env_override == "1":
        return True
    if env_override == "0":
        return False

    # CI 环境不启用（无桌面会话）
    if os.environ.get("CI", "") == "true":
        return False

    # 本地环境：pywinauto 已安装则自动启用
    try:
        import pywinauto  # noqa: F401

        return True
    except ImportError:
        return False


_USE_PYWAUTO = _should_use_pywinauto()


# ════════════════════════════════════════════════════════════════
# Session 级 QMessageBox 静态方法统一 patch
# ════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True, scope="session")
def _auto_patch_qmessagebox():
    """Session 级 patch：QMessageBox 静态方法全部返回预设值。

    QFileDialog 不在此处 patch——由 pywinauto 后台线程（或降级 mock）处理。
    """
    patchers = [
        patch("PyQt6.QtWidgets.QMessageBox.information", return_value=QMessageBox.StandardButton.Ok),
        patch("PyQt6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.StandardButton.Ok),
        patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
        patch("PyQt6.QtWidgets.QMessageBox.critical", return_value=QMessageBox.StandardButton.Ok),
        patch("PyQt6.QtWidgets.QMessageBox.about", return_value=None),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


# ════════════════════════════════════════════════════════════════
# Session 级 QMenu.exec / exec_ 自动关闭 patch
# ════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True, scope="session")
def _auto_patch_qmenu_exec():
    """Session 级 patch：QMenu.exec / exec_ 弹出后立即关闭，避免阻塞测试。

    QMenu.exec() 进入本地事件循环等待用户交互，SmartDialogInterceptor 不拦截
    QMenu（只处理 QDialog / QMessageBox），导致测试永久卡死。
    通过 QTimer.singleShot(0, self.close) 在菜单事件循环的下一轮自动关闭。

    设置 PILOTSTD_REAL_QMENU=1 可恢复真实 QMenu 行为（用于需要验证菜单交互的测试）。
    """
    if os.environ.get("PILOTSTD_REAL_QMENU") == "1":
        yield
        return

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMenu

    _original_exec = QMenu.exec
    _original_exec_ = getattr(QMenu, "exec_", None)

    def _patched_exec(self: QMenu, *args: object, **kwargs: object) -> object:
        QTimer.singleShot(0, self.close)
        return _original_exec(self, *args, **kwargs)

    QMenu.exec = _patched_exec  # type: ignore[method-assign]
    if _original_exec_ is not None:
        QMenu.exec_ = _patched_exec  # type: ignore[method-assign]

    yield

    QMenu.exec = _original_exec  # type: ignore[method-assign]
    if _original_exec_ is not None:
        QMenu.exec_ = _original_exec_  # type: ignore[method-assign]


# ════════════════════════════════════════════════════════════════
# Session 级 QFileDialog 降级 patch（pywinauto 不可用时）
# ════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True, scope="session")
def _auto_patch_qfiledialog_fallback():
    """Session 级 QFileDialog 降级 patch。

    仅当 pywinauto 不可用时启用，用 mock patch 替代真实文件对话框。
    """
    if _USE_PYWAUTO:
        yield
        return

    logger = logging.getLogger("pilotstd.ui")
    if _USE_PYWAUTO:
        logger.info("[DialogHandler] pywinauto 模式已启用，文件对话框将由后台守护线程处理。")
    else:
        logger.warning(
            "[DialogHandler] pywinauto 未启用 (PILOTSTD_USE_PYWAUTO=%s)，"
            "QFileDialog 降级为 mock patch。"
            "设置 PILOTSTD_USE_PYWAUTO=1 可启用真实文件对话框交互测试。",
            os.environ.get("PILOTSTD_USE_PYWAUTO", "0"),
        )

    patchers = [
        patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", return_value=_MOCK_DIR),
        patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=(_MOCK_FILE, "")),
        patch("PyQt6.QtWidgets.QFileDialog.getOpenFileNames", return_value=([_MOCK_FILE], "")),
        patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(_MOCK_FILE, "")),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()

    try:
        shutil.rmtree(_TMPDIR, ignore_errors=True)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# Session 级 pywinauto 后台守护线程（只启动一次）
# ════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True, scope="session")
def _auto_handle_filedialog_session(qapp):
    """Session 级：pywinauto 后台守护线程，处理所有 QFileDialog 弹窗。

    只创建一次 Desktop(backend="uia")，避免每个测试函数重复初始化。
    """
    from tests.gui.helpers.dialog_handler import FileDialogAutoHandler

    file_handler: FileDialogAutoHandler | None = None
    if _USE_PYWAUTO:
        file_handler = FileDialogAutoHandler(
            target_dir=_MOCK_DIR,
            target_file=_MOCK_FILE,
            timeout=600.0,  # session 级别长超时
        )
        file_handler.start()

    yield

    if file_handler is not None:
        file_handler.stop()


# ════════════════════════════════════════════════════════════════
# Function 级 Qt 事件过滤器（每个测试安装/移除）
# ════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _auto_handle_qt_dialogs(qapp):
    """每个测试函数安装 SmartDialogInterceptor，处理后移除。

    只处理 Qt 内部弹窗（QMessageBox 实例 + 自定义 QDialog），非常轻量。
    """
    from tests.gui.helpers.dialog_handler import SmartDialogInterceptor

    interceptor = SmartDialogInterceptor(auto_accept=True)
    qapp.installEventFilter(interceptor)

    yield

    qapp.removeEventFilter(interceptor)


# ════════════════════════════════════════════════════════════════
# 网络阻断（session）
# ════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True, scope="session")
def _block_all_network_requests():
    """阻断 GUI 测试中的所有真实 HTTP 请求。"""
    if os.environ.get("PILOTSTD_ALLOW_NETWORK") == "1":
        yield
        return
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, re.compile(r".*"), status=500)
        rsps.add(responses.POST, re.compile(r".*"), status=500)
        rsps.add(responses.OPTIONS, re.compile(r".*"), status=500)
        rsps.add(responses.PUT, re.compile(r".*"), status=500)
        rsps.add(responses.DELETE, re.compile(r".*"), status=500)
        yield


# ════════════════════════════════════════════════════════════════
# 模板 DB（session）
# ════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def _template_db_path(tmp_path_factory):
    """Session 级模板 DB：37 个迁移只跑一次。"""
    from pilotstd.core.db import Database

    template_dir = tmp_path_factory.mktemp("db_template")
    db_path = str(template_dir / "template.db")
    db = Database(db_path)
    db.close_all()
    return db_path


# ════════════════════════════════════════════════════════════════
# QApplication（session）
# ════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setStyle("Fusion")
    yield app


# ════════════════════════════════════════════════════════════════
# 测试数据目录
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def test_data_dir():
    """返回 fixtures 目录路径。"""
    return os.path.join(os.path.dirname(__file__), "fixtures")


# ════════════════════════════════════════════════════════════════
# Mock MainWindow（function）
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_main_window(qapp, qtbot, test_data_dir, _template_db_path):
    """创建 mock 模式下的 MainWindow。"""
    tmpdir = tempfile.mkdtemp(prefix="pilotstd_gui_test_")

    db_path = os.path.join(tmpdir, "test.db")
    shutil.copy2(_template_db_path, db_path)

    config_path = os.path.join(tmpdir, "config.json")
    cfg = core.ConfigManager(filepath=config_path)
    cfg.set("query.use_cache", False)
    cfg.set("query.use_announcement_match", False)
    cfg.set("storage.root_dir", os.path.join(tmpdir, "library"))
    cfg.set("appearance.skip_welcome", True)

    prj = core.ProjectManager()
    window = MainWindow(cfg, prj)

    from pilotstd.core.db import Database
    from pilotstd.download.engine import DownloadEngine
    from pilotstd.download.session import SessionManager
    from pilotstd.query.cache import CacheRepository
    from pilotstd.query.engine import QueryEngine
    from tests.adapters.mock import MockQueryAdapter
    from tests.adapters.mock_download import MockDownloadAdapter

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
    window._suppress_dialogs = True
    window.show()
    qtbot.addWidget(window)
    qtbot.waitExposed(window)

    yield window

    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if hasattr(window, "_log_handler") and h is window._log_handler:
            root_logger.removeHandler(h)

    if hasattr(window, "_mgr") and window._mgr is not None:
        fi = window._mgr._core.file_index
        if fi is not None:
            fi.stop()

    if hasattr(window, "_stop_workers"):
        window._stop_workers()
    window.close()
    window.deleteLater()
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def window(mock_main_window):
    """别名。"""
    return mock_main_window


# ════════════════════════════════════════════════════════════════
# 真实网络 MainWindow（冷启模拟）
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def real_window(qapp, qtbot, _template_db_path):
    """创建真实网络模式下的 MainWindow。"""
    _tmp = tempfile.mkdtemp(prefix="stress_cold_")

    db_path = os.path.join(_tmp, "test.db")
    shutil.copy2(_template_db_path, db_path)

    config_path = os.path.join(_tmp, "config.json")
    cfg = core.ConfigManager(filepath=config_path)
    cfg.set("query.use_cache", True)
    cfg.set("storage.root_dir", os.path.join(_tmp, "library"))
    cfg.set("appearance.skip_welcome", True)
    cfg.set("announcement.auto_check", False)

    prj = core.ProjectManager()
    win = MainWindow(cfg, prj)
    win._suppress_dialogs = True
    win.show()
    qtbot.addWidget(win)
    qtbot.waitExposed(win)

    yield win

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
