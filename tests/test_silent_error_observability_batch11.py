"""静默吞错第 11 批：OCR 线程优先级失败可见性（体检 D-8，仅 Windows）。

`_set_thread_priority_idle` 在 SetThreadPriority 不可用时原 pass；现记 debug。
"""

from __future__ import annotations

import logging
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="thread priority API 仅 Windows")


def test_set_thread_priority_failure_logs(monkeypatch, caplog) -> None:
    import ctypes

    from pilotstd.announcement.ocr._pdf_utils import _set_thread_priority_idle

    class _BrokenWindll:
        @property
        def kernel32(self):
            raise AttributeError("windll unavailable")

    monkeypatch.setattr(ctypes, "windll", _BrokenWindll(), raising=False)

    with caplog.at_level(logging.DEBUG, logger="pilotstd.announcement.ocr._pdf_utils"):
        _set_thread_priority_idle()
    assert "set OCR thread priority failed" in caplog.text
