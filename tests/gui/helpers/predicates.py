"""Reusable UI predicates for wait_for_worker_and_ui."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class HasWorkTable(Protocol):
    """Minimal protocol for windows exposing a work_table widget."""

    @property
    def work_table(self) -> object: ...


@runtime_checkable
class HasStatusLabel(Protocol):
    """Minimal protocol for windows exposing a status_label widget."""

    @property
    def status_label(self) -> object: ...


def thread_finished(worker: Any) -> bool:
    """worker 是否已**真正**结束（与 `pilotstd.ui.qt_lifecycle._thread_finished` 同判据）。

    判据必须是 `isFinished()`：`QThread.start()` 之后存在「已启动但尚未进入 run()」的窗口，
    此时 `isRunning()` 仍为 False——用它会把仍在运行的线程判成已结束（引用一丢就 Qt qFatal）。
    鸭子类型替身（只有 `isRunning()` 的测试假 worker）退回「未在运行」判据。
    """
    try:
        return bool(worker.isFinished())
    except (AttributeError, RuntimeError):
        return not worker.isRunning()


def worker_finished(worker: Any) -> Callable[[], bool]:
    """返回「该 worker 已结束」的谓词（绑定具体 worker 实例）。"""

    def _finished() -> bool:
        return thread_finished(worker)

    return _finished


class _WorkerDoneSentinel:
    """`worker_done` 哨兵：交给 `wait_for_worker_and_ui` 表示"等这个 worker 结束"。

    真正的判定必须绑定具体 worker，所以由 helper 用 `worker_finished(worker)` 实例化。
    本对象**刻意不可调用**——若被当作普通谓词直接传给 `qtbot.waitUntil(...)`，
    会立刻 `TypeError: '...' object is not callable`，而不会像旧实现那样"恒返回 True"
    把等待变成空操作。
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "worker_done"


#: 旧 API 的兼容名：过去是"恒返回 True"的函数，导致所有等待空转；现为哨兵对象。
worker_done = _WorkerDoneSentinel()


def table_has_rows(window: HasWorkTable, *, min_rows: int = 1) -> bool:
    """True when work_table has at least min_rows rows."""
    return window.work_table.rowCount() >= min_rows  # type: ignore[union-attr]


def status_contains(window: HasStatusLabel, text: str) -> bool:
    """True when status_label contains the given substring."""
    return text in window.status_label.text()  # type: ignore[union-attr]


def file_exists(path: str | Path) -> bool:
    """True when the specified file exists on disk."""
    return Path(path).exists()


def progress_complete(
    window: object, *, attr: str = "archive_progress_bar", threshold: int = 100
) -> bool:
    """True when a progress bar widget reaches the threshold."""
    bar = getattr(window, attr, None)
    return bar is not None and hasattr(bar, "value") and bar.value() >= threshold
