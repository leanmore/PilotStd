"""P3-16 可本地化的并发部分：manager 单例 + file_index 写竞争。

真实 Docker 的通知渠道/进程间锁仍属外部；本文件只锁定：
- 100 个文件事件并发时，懒加载 manager 只构造一次；
- 100 线程对同一 file_path upsert 不抛 UNIQUE/locked，最终一行。
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from pilotstd.core.db import Database
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.monitor.scheduler import FileMonitorScheduler


def test_100_concurrent_file_events_construct_one_manager(tmp_path):
    dirs = []
    for i in range(100):
        d = tmp_path / f"d{i}"
        d.mkdir()
        f = d / f"GB {i + 1}-2020 测试.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        dirs.append(f)

    instances = []

    class FakeManager:
        def __init__(self):
            instances.append(self)

        def auto_run(self, root_path):
            return {"scan": 1, "organize_moved": 1}

    scheduler = FileMonitorScheduler()
    with patch("pilotstd.monitor.scheduler.get_config", return_value={"auto_archive": True}), patch(
        "pilotstd.monitor.scheduler.get_monitor_stats", return_value=MagicMock()
    ), patch("pilotstd.manager.facade.StandardManager", FakeManager):
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(scheduler._on_file, [str(p) for p in dirs]))

    assert len(instances) == 1, len(instances)
    assert scheduler._mgr is instances[0]


def test_100_concurrent_upserts_same_path_do_not_raise(tmp_path):
    os.environ["PILOTSTD_TEST_MODE"] = "1"
    db = Database(str(tmp_path / "concurrent.db"))
    repo = FileIndexRepository(db)
    path = tmp_path / "same.pdf"
    path.write_bytes(b"%PDF-1.4 fake")

    def write_one(i: int) -> None:
        repo.upsert(
            file_path=str(path),
            logical_code="GB",
            number=19001,
            year=2020,
            std_name="并发测试",
        )

    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(write_one, range(100)))
        rows = db.fetchall("SELECT file_path FROM file_index WHERE file_path=?", (str(path),))
        assert len(rows) == 1, rows
    finally:
        repo.stop()
