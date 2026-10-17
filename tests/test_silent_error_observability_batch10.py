"""静默吞错第 10 批：入队失败可见性（体检 D-8）。

`ValidityService.enqueue_files` 单条入队失败原 pass（返回的 enqueued 少算但无痕迹）。
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from pilotstd.manager.validity_service import ValidityService


def test_enqueue_files_failure_logs(caplog) -> None:
    db = MagicMock()
    db.execute.side_effect = RuntimeError("queue insert failed")
    service = ValidityService(SimpleNamespace(db=db))

    with caplog.at_level(logging.WARNING, logger="pilotstd.manager.validity_service"):
        result = service.enqueue_files(["/tmp/a.pdf", "/tmp/b.pdf"])

    assert result == {"ok": True, "enqueued": 0, "total": 2}
    assert "enqueue validity file failed" in caplog.text
