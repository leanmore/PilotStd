"""启动/关停路径的吞错治理（体检 D-11）。

原实现 5 处 `except Exception: pass`：
- `_clean_zombie_tasks`：僵尸任务清理失败无任何痕迹；
- 任务调度器启动失败 → 服务在线但任务永不执行（最严重）；
- 企业微信调度器启动/停止失败无痕迹；
- 任务调度器停止失败无痕迹。

修复后：启动路径关键失败 **fail-fast**（任务调度器），其余记 warning 且不阻断。
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from docker import app as app_module


class _FakeTaskScheduler:
    def __init__(self) -> None:
        self.queue = None
        self.started = False
        self.stopped = False
        self.fail_start = False
        self.fail_stop = False

    def set_queue(self, queue) -> None:
        self.queue = queue

    def start(self) -> None:
        if self.fail_start:
            raise RuntimeError("scheduler start boom")
        self.started = True

    def stop(self) -> None:
        if self.fail_stop:
            raise RuntimeError("scheduler stop boom")
        self.stopped = True


@pytest.fixture()
def fake_task_scheduler(monkeypatch) -> _FakeTaskScheduler:
    fake = _FakeTaskScheduler()
    import pilotstd.task.scheduler as task_scheduler

    monkeypatch.setattr(task_scheduler, "get_scheduler", lambda: fake)
    return fake


def test_start_task_scheduler_binds_queue_and_starts(fake_task_scheduler) -> None:
    mgr = SimpleNamespace(task_queue="queue-obj")
    app_module._start_task_scheduler(mgr)
    assert fake_task_scheduler.queue == "queue-obj"
    assert fake_task_scheduler.started is True


def test_start_task_scheduler_propagates_failure(fake_task_scheduler) -> None:
    """启动失败必须抛出（lifespan 据此 fail-fast），不得被吞成'服务已就绪'。"""
    fake_task_scheduler.fail_start = True
    with pytest.raises(RuntimeError, match="scheduler start boom"):
        app_module._start_task_scheduler(SimpleNamespace(task_queue=None))


def test_clean_zombie_tasks_logs_warning_on_failure(monkeypatch, caplog) -> None:
    class _BrokenDatabase:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("db unavailable")

    import pilotstd.core.config as core_config
    import pilotstd.core.db as core_db

    monkeypatch.setattr(core_db, "Database", _BrokenDatabase)
    monkeypatch.setattr(core_config, "get_db_path", lambda: "unused.db")

    with caplog.at_level(logging.WARNING, logger="docker.app"):
        app_module._clean_zombie_tasks()  # 不阻断启动

    assert "zombie task cleanup failed" in caplog.text


def test_shutdown_cleanup_never_raises(monkeypatch, caplog, fake_task_scheduler) -> None:
    """关停阶段任一服务失败都只记 warning，不能阻断其余清理。"""
    fake_task_scheduler.fail_stop = True

    monitor = SimpleNamespace(
        stop_scheduler=lambda: (_ for _ in ()).throw(RuntimeError("monitor boom"))
    )
    wechat = SimpleNamespace(
        stop_scheduler=lambda: (_ for _ in ()).throw(RuntimeError("wechat boom"))
    )
    mgr = SimpleNamespace(monitor_service=monitor, wechat_ip_service=wechat, shutdown=lambda: None)

    monkeypatch.setattr(app_module, "stop_scheduler", lambda: None)

    with caplog.at_level(logging.WARNING, logger="docker.app"):
        app_module._shutdown_cleanup(mgr)

    assert "monitor boom" in caplog.text
    assert "wechat boom" in caplog.text
    assert "scheduler stop boom" in caplog.text
