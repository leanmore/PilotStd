# tests/gui/test_cleanup_error_channel.py
"""W1-U1 回归：FileMoveWorker.error_occurred → CleanupHandler._status 链路。"""

from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QObject, pyqtSignal

from pilotstd.ui.core.handlers._cleanup import CleanupHandler


class _FakeProgress(QObject):
    """QProgressDialog 替身：只需 canceled 信号与 move_unrecognized_files 用到的方法。"""

    canceled = pyqtSignal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()

    def setWindowModality(self, *args) -> None:
        pass

    def setMinimumDuration(self, *args) -> None:
        pass

    def setValue(self, *args) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeWorker(QObject):
    """FileMoveWorker 替身：start() 时依次发 error_occurred / move_done / finished。"""

    progress_changed = pyqtSignal(int)
    move_done = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, selected, root_dir, parent=None) -> None:
        super().__init__()
        self.selected = selected

    def start(self) -> None:
        self.error_occurred.emit("搬迁失败: boom")
        self.move_done.emit(1)
        self.finished.emit()

    def deleteLater(self) -> None:
        pass

    def requestInterruption(self) -> None:
        pass


class _FakeLoop:
    """QEventLoop 替身：worker.start() 已同步发完信号，exec 直接返回。"""

    def quit(self) -> None:
        pass

    def exec(self) -> int:
        return 0


def test_error_occurred_reaches_status_callback(qtbot, monkeypatch):
    """模拟搬迁失败：断言 CleanupHandler._status 收到错误文案，且 moved 计数仍返回。"""
    messages: list[str] = []
    status = messages.append
    handler = CleanupHandler(
        config=SimpleNamespace(get=lambda *args, **kwargs: None),
        status_callback=status,
        question_dlg=lambda *args, **kwargs: None,
        get_library_root=lambda: "/tmp/library",
        get_unrecognized_files=lambda: [],
        clear_unrecognized_files=lambda: None,
        get_scan_source_root=lambda: "/tmp",
        parent=None,
    )

    # 直接钉住“self._status 就是构造注入的 status_callback”（属性名若被改会立即失败）
    assert handler._status is status

    monkeypatch.setattr("pilotstd.ui.core.handlers._cleanup.FileMoveWorker", _FakeWorker)
    monkeypatch.setattr("pilotstd.ui.core.handlers._cleanup.QProgressDialog", _FakeProgress)
    monkeypatch.setattr("PyQt6.QtCore.QEventLoop", _FakeLoop)

    moved = handler.move_unrecognized_files([("/tmp/src.pdf", "src.pdf")], parent=None)

    assert messages == ["搬迁失败: boom"]
    assert moved == 1
