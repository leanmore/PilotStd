# tests/gui/helpers/dialog_handler.py
"""混合弹窗处理方案。

QFileDialog（Windows 原生 #32770）→ pywinauto 后台守护线程。
QMessageBox/自定义 QDialog（Qt 内部）→ SmartDialogInterceptor 事件过滤器。

若 pywinauto 不可用，自动降级为 pytest-mock patch（不中断测试）。
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from typing import Optional
from unittest.mock import patch

from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QPushButton,
)

logger = logging.getLogger(__name__)

# ── pywinauto 可用性检测（不触发 import，避免 COM STA 警告）──

import importlib.util as _importlib_util

_PYWAUTO_SPEC = _importlib_util.find_spec("pywinauto")
PYWAUTO_AVAILABLE = _PYWAUTO_SPEC is not None
PYWAUTO_ERROR: Optional[str] = None if PYWAUTO_AVAILABLE else "pywinauto 未安装"

# ── 降级用临时目录 ──────────────────────────────────────────

_FALLBACK_DIR = tempfile.mkdtemp(prefix="pilotstd_fallback_")
_FALLBACK_FILE = os.path.join(_FALLBACK_DIR, "mock.file")
os.makedirs(_FALLBACK_DIR, exist_ok=True)
with open(_FALLBACK_FILE, "w") as _f:
    _f.write("mock")


# ════════════════════════════════════════════════════════════════
# 文件对话框处理器（pywinauto 后台守护线程）
# ════════════════════════════════════════════════════════════════


class FileDialogAutoHandler:
    """后台守护线程：监听 Windows 原生文件对话框 (#32770) 并自动操作。

    关键设计：
      - daemon=True：主线程被 QFileDialog 阻塞时，此线程仍在运行
      - _stop_event：线程安全的停止信号
      - 每次 _listen_loop 迭代重建 Desktop 引用，避免跨线程引用失效
      - 标题关键词匹配 i18n 翻译
    """

    # ── 标题关键词（中英文 i18n）──
    TITLE_KEYWORDS = [
        "选择",
        "打开",
        "保存",
        "导出",
        "导入",
        "另存为",
        "Select",
        "Open",
        "Save",
        "Export",
        "Import",
    ]

    # ── 按钮文本关键词（优先级从高到低）──
    BUTTON_KEYWORDS = [
        "选择文件夹",
        "Select Folder",
        "打开",
        "Open",
        "保存",
        "Save",
        "确定",
        "OK",
        "是",
        "Yes",
    ]

    def __init__(
        self,
        target_dir: str = _FALLBACK_DIR,
        target_file: str = _FALLBACK_FILE,
        timeout: float = 10.0,
    ) -> None:
        self.target_dir = target_dir
        self.target_file = target_file
        self.timeout = timeout
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动后台监听线程。必须在任何可能触发 QFileDialog 的操作之前调用。"""
        if not PYWAUTO_AVAILABLE:
            logger.warning(
                "FileDialogAutoHandler: pywinauto 不可用 (%s)，QFileDialog 将走降级 patch。",
                PYWAUTO_ERROR,
            )
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="pywinauto-listener")
        self._thread.start()
        logger.info("[Pywinauto] 后台监听已启动 target_dir=%s", self.target_dir)

    def stop(self) -> None:
        """停止监听线程。"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("[Pywinauto] 后台监听已停止")

    def _listen_loop(self) -> None:
        """后台轮询主循环。每 0.3s 扫描一次桌面窗口。"""
        from pywinauto import Desktop  # type: ignore[import-untyped]  # 懒加载，避免 COM STA 警告

        deadline = time.time() + self.timeout
        desktop = Desktop(backend="uia")

        while not self._stop_event.is_set() and time.time() < deadline:
            try:
                for win in desktop.windows():
                    try:
                        title = win.window_text()
                    except Exception:
                        continue

                    if not title or not any(kw in title for kw in self.TITLE_KEYWORDS):
                        continue

                    edit = self._find_edit(win)
                    if edit is None:
                        continue

                    logger.info("[Pywinauto] 捕获文件对话框: %s", title)
                    self._fill_and_confirm(win, edit)
                    break  # 处理完一个，本轮结束
            except Exception:
                pass

            self._stop_event.wait(0.3)

    @staticmethod
    def _find_edit(window):
        """在窗口中查找文件名/地址栏编辑框。

        Windows 10/11 文件对话框编辑框的定位策略：
          1. 查找 name 含 "文件名" / "File name" / "文件夹" 的 Edit
          2. 回退：查找 ComboBox 中的 Edit
          3. 回退：获取第一个可见 Edit
        """
        try:
            for edit in window.descendants(control_type="Edit"):
                try:
                    name = edit.element_info.name or ""
                    if any(kw in name for kw in ("文件名", "File name", "文件夹", "Folder", "地址")):
                        return edit
                except Exception:
                    continue
        except Exception:
            pass

        # 回退：ComboBox → Edit
        try:
            combo = window.child_window(class_name="ComboBoxEx32")
            return combo.child_window(control_type="Edit")
        except Exception:
            pass

        # 最后回退：第一个可见 Edit
        try:
            for edit in window.descendants(control_type="Edit"):
                if edit.is_visible():
                    return edit
        except Exception:
            pass

        return None

    def _fill_and_confirm(self, window, edit) -> None:
        """输入路径并点击确认按钮。"""
        # 判断是文件夹选择器还是文件选择器
        try:
            title = window.window_text()
            is_folder = any(kw in title for kw in ("文件夹", "目录", "Folder", "Directory"))
        except Exception:
            is_folder = True

        target = self.target_dir if is_folder else self.target_file

        try:
            window.set_focus()
            time.sleep(0.2)
            edit.set_focus()
            edit.set_text(target)
            time.sleep(0.3)
            edit.type_keys("{ENTER}")
            time.sleep(0.3)
        except Exception as e:
            logger.debug("[Pywinauto] 编辑框输入失败: %s，尝试回退", e)

        self._click_confirm(window)

    def _click_confirm(self, window) -> None:
        """按优先级点击确认按钮。"""
        for kw in self.BUTTON_KEYWORDS:
            try:
                btn = window.child_window(title=kw, control_type="Button")
                if btn.exists(timeout=1):
                    btn.click_input()
                    logger.info("[Pywinauto] 已点击按钮: %s", kw)
                    return
            except Exception:
                continue

        # 最后回退：回车
        try:
            window.type_keys("{ENTER}")
            logger.info("[Pywinauto] 已发送回车")
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
# 增强型 Qt 事件过滤器
# ════════════════════════════════════════════════════════════════


class SmartDialogInterceptor(QObject):
    """全局事件过滤器：拦截并自动处理 Qt 内部弹窗。

    优于旧 ModalDialogAutoClicker 的改进：
      - 通过 _handled set 防止重复处理
      - QTimer.singleShot(50) 确保控件渲染完成
      - 不依赖 qtbot.mouseClick（避免 teardown 竞态）
      - 直接调用 btn.click() 而非模拟鼠标
    """

    # i18n 按钮文本映射
    ACCEPT_TEXTS = {"确定", "是", "OK", "Yes", "btn_ok", "btn_yes", "关闭", "Close", "开始使用", "Get Started"}
    REJECT_TEXTS = {"取消", "否", "Cancel", "No", "btn_cancel", "btn_no"}

    def __init__(self, auto_accept: bool = True) -> None:
        super().__init__()
        self.auto_accept = auto_accept
        self._handled: set[int] = set()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.Show:
            if isinstance(obj, (QDialog, QMessageBox)) and id(obj) not in self._handled:
                self._handled.add(id(obj))
                QTimer.singleShot(50, lambda: self._process(obj))
        return super().eventFilter(obj, event)

    def _process(self, dialog: QDialog) -> None:
        """分发处理。"""
        if not self.auto_accept or not dialog.isVisible():
            return

        try:
            # 1. QDialogButtonBox
            button_box = dialog.findChild(QDialogButtonBox)
            if button_box is not None:
                for std in (
                    QDialogButtonBox.StandardButton.Ok,
                    QDialogButtonBox.StandardButton.Yes,
                    QDialogButtonBox.StandardButton.Close,
                ):
                    btn = button_box.button(std)
                    if btn and btn.isEnabled() and btn.isVisible():
                        btn.click()
                        logger.debug("[Interceptor] QDialogButtonBox: %s", std)
                        return

            # 2. QPushButton — 优先匹配 ACCEPT_TEXTS
            for btn in dialog.findChildren(QPushButton):
                if not btn.isEnabled() or not btn.isVisible():
                    continue
                if btn.text().strip() in self.ACCEPT_TEXTS:
                    btn.click()
                    logger.debug("[Interceptor] accept 按钮: %s", btn.text())
                    return

            # 3. QMessageBox — 点击默认按钮
            if isinstance(dialog, QMessageBox):
                default_btn = dialog.defaultButton()
                if default_btn and default_btn.isEnabled():
                    default_btn.click()
                    return
                for btn in dialog.buttons():  # type: ignore[assignment]
                    if btn.isEnabled():  # type: ignore[union-attr]
                        btn.click()  # type: ignore[union-attr]
                        return

            # 4. 最后手段：accept
            dialog.accept()
            logger.debug("[Interceptor] 强制 accept: %s", type(dialog).__name__)
        except Exception as e:
            logger.debug("[Interceptor] 处理失败: %s", e)


# ════════════════════════════════════════════════════════════════
# 降级逃生通道
# ════════════════════════════════════════════════════════════════


def get_qfiledialog_patches():
    """QFileDialog mock patch 列表。"""
    return [
        patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", return_value=_FALLBACK_DIR),
        patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=(_FALLBACK_FILE, "")),
        patch("PyQt6.QtWidgets.QFileDialog.getOpenFileNames", return_value=([_FALLBACK_FILE], "")),
        patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(_FALLBACK_FILE, "")),
    ]


def get_qmessagebox_patches():
    """QMessageBox mock patch 列表。"""
    return [
        patch("PyQt6.QtWidgets.QMessageBox.information", return_value=QMessageBox.StandardButton.Ok),
        patch("PyQt6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.StandardButton.Ok),
        patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
        patch("PyQt6.QtWidgets.QMessageBox.critical", return_value=QMessageBox.StandardButton.Ok),
        patch("PyQt6.QtWidgets.QMessageBox.about", return_value=None),
    ]
