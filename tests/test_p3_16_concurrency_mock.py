"""P3-16 可本地化的并发部分：manager 单例 + file_index 写竞争。

真实 Docker 的通知渠道/进程间锁仍属外部；本文件只锁定：
- 100 个文件事件并发时，懒加载 manager 只构造一次；
- 100 线程对同一 file_path upsert 不抛 UNIQUE/locked，最终一行。
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pilotstd.monitor.scheduler as scheduler_module
from pilotstd.core.db import Database
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.monitor.handler import StandardFileHandler
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


def test_100_timer_callbacks_construct_one_manager(tmp_path):
    """真实 Timer 时序：每个文件事件一个 Timer，回调共享同一个 scheduler。"""
    files = []
    for i in range(100):
        d = tmp_path / f"timer{i}"
        d.mkdir()
        f = d / f"GB {i + 1}-2020 测试.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        files.append(f)

    instances = []
    calls = 0
    calls_lock = threading.Lock()

    class FakeManager:
        def __init__(self):
            instances.append(self)

        def auto_run(self, root_path):
            nonlocal calls
            with calls_lock:
                calls += 1
            return {"scan": 1, "organize_moved": 1}

    scheduler = FileMonitorScheduler()
    cfg = {
        "auto_archive": True,
        "watch_path": str(tmp_path),
        "file_patterns": [".pdf"],
        "ignore_patterns": [],
    }
    with patch("pilotstd.monitor.handler.get_config", return_value=cfg), patch(
        "pilotstd.monitor.scheduler.get_config", return_value=cfg
    ), patch(
        "pilotstd.monitor.scheduler.get_monitor_stats", return_value=MagicMock()
    ), patch(
        "pilotstd.manager.facade.StandardManager", FakeManager
    ):
        handler = StandardFileHandler(callback=scheduler._on_file, delay_seconds=0)
        for f in files:
            handler.on_created(SimpleNamespace(is_directory=False, src_path=str(f)))

        deadline = time.monotonic() + 5
        while calls < 100 and time.monotonic() < deadline:
            time.sleep(0.01)

    assert calls == 100, calls
    assert len(instances) == 1, len(instances)
    assert scheduler._mgr is instances[0]


def test_100_concurrent_get_scheduler_returns_one(monkeypatch):
    """get_scheduler 单例竞态：100 线程同时首次获取只能构造一个。"""
    constructed = []

    class FakeScheduler:
        def __init__(self):
            constructed.append(self)

    monkeypatch.setattr(scheduler_module, "_instance", None)
    monkeypatch.setattr(scheduler_module, "FileMonitorScheduler", FakeScheduler)
    with ThreadPoolExecutor(max_workers=100) as pool:
        result = list(pool.map(lambda _: scheduler_module.get_scheduler(), range(100)))

    assert len(constructed) == 1, len(constructed)
    assert len({id(x) for x in result}) == 1


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
