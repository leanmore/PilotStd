"""#7 Web B：下载任务落 task_queue 与重启重试。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from pilotstd.download.engine import DownloadEngine
from pilotstd.download.models import DownloadStatus, DownloadTask


class _Db:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return type("_C", (), {"rowcount": 1})()

    def fetchall(self, sql, params=()):
        return self.rows


def _engine(db):
    return DownloadEngine([], MagicMock(), db=db)


def test_persist_task_writes_task_queue():
    db = _Db()
    engine = _engine(db)
    task = DownloadTask(
        standard_number="GB/T 1-2020",
        source_site="openstd_download",
        status=DownloadStatus.FAILED,
        error_message="boom",
    )
    engine._persist_task(task)
    sql, params = db.executed[0]
    assert "task_queue" in sql
    assert params[1] == "failed"
    payload = json.loads(params[6])
    assert payload["standard_number"] == "GB/T 1-2020"
    assert payload["error_message"] == "boom"


def test_retry_pending_rebuilds_and_calls_batch():
    payload = json.dumps(
        {
            "standard_number": "GB/T 2-2021",
            "source_site": "openstd_download",
            "retry_count": 1,
            "max_retries": 3,
        }
    )
    db = _Db([{"task_id": "download:x", "status": "failed", "result_json": payload, "error_log": "x"}])
    engine = _engine(db)
    engine.download_batch = MagicMock(return_value=([], MagicMock()))

    assert engine.retry_pending() == 1
    tasks = engine.download_batch.call_args[0][0]
    assert tasks[0].standard_number == "GB/T 2-2021"
    assert tasks[0].retry_count == 2
    assert tasks[0].max_retries == 3


def test_retry_pending_stops_at_max_retries():
    payload = json.dumps(
        {
            "standard_number": "GB/T 3-2022",
            "retry_count": 3,
            "max_retries": 3,
        }
    )
    db = _Db([{"task_id": "download:y", "status": "failed", "result_json": payload, "error_log": "x"}])
    engine = _engine(db)
    engine.download_batch = MagicMock()

    assert engine.retry_pending() == 0
    engine.download_batch.assert_not_called()
