"""Reusable UI predicates for wait_for_worker_and_ui."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


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


def worker_done() -> bool:
    """Universal fallback: unconditionally signals worker completion."""
    return True


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
