"""下载任务持久化的 task_id 指纹契约。"""

from __future__ import annotations

import hashlib

from pilotstd.download.models import DownloadStatus, DownloadTask
from pilotstd.download.task_store import DownloadTaskStore


class _FakeDB:
    """只记录 execute 参数，不连真实 task_queue。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple) -> None:
        self.calls.append((sql, params))


def test_persist_task_id_is_stable_non_security_fingerprint() -> None:
    db = _FakeDB()
    task = DownloadTask("GB/T 1-2020", source_site="example")
    task.status = DownloadStatus.SUCCESS

    DownloadTaskStore(db).persist(task)

    expected = "download:" + hashlib.sha1(
        b"example|GB/T 1-2020", usedforsecurity=False
    ).hexdigest()[:16]
    assert db.calls[0][1][0] == expected
    assert db.calls[0][1][2] == 1  # completed_items
