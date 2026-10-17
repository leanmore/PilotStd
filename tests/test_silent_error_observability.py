"""静默吞错的可见性回归（体检 D-8/D-9，2026-10-17 第 1 批）。

覆盖两处此前无任何痕迹的失败：
- `Database` 的适配器统计读写（写失败/读失败都返回默认值，等于"数据没坏"）；
- `docker/scheduler.py` 的锁心跳解析、心跳写失败、关停释放锁失败。
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def db(tmp_path):
    from pilotstd.core.db import Database

    database = Database(str(tmp_path / "silent.db"))
    yield database
    database.close()


def test_record_adapter_result_failure_logs(db, caplog) -> None:
    db.execute = MagicMock(side_effect=RuntimeError("db down"))
    with caplog.at_level(logging.WARNING, logger="pilotstd.db"):
        db.update_adapter_stats("std_gov", success=True)
    assert "record_adapter_result failed" in caplog.text


def test_adapter_success_rate_failure_logs_and_returns_sentinel(db, caplog) -> None:
    db.fetchone = MagicMock(side_effect=RuntimeError("db down"))
    with caplog.at_level(logging.WARNING, logger="pilotstd.db"):
        assert db.get_adapter_success_rate("std_gov") == -1.0
    assert "get_adapter_success_rate failed" in caplog.text


def test_adapter_stats_all_failure_logs_and_returns_empty(db, caplog) -> None:
    db.fetchall = MagicMock(side_effect=RuntimeError("db down"))
    with caplog.at_level(logging.WARNING, logger="pilotstd.db"):
        assert db.get_adapter_stats_all() == []
    assert "get_adapter_stats_all failed" in caplog.text


# ── docker/scheduler.py ──────────────────────────────────────────────


def test_scheduler_lock_unparsable_heartbeat_logs(monkeypatch, caplog) -> None:
    from docker import scheduler as sched

    fake_db = MagicMock()
    # 第一次 execute 是建表（成功），第二次 INSERT 才失败
    fake_db.execute.side_effect = [None, RuntimeError("insert conflict")]
    fake_db.fetchone.return_value = {"pid": 1, "heartbeat_at": "not-a-time"}
    monkeypatch.setattr(sched, "_get_db", lambda: fake_db)

    with caplog.at_level(logging.WARNING, logger="docker.scheduler"):
        assert sched._acquire_scheduler_lock() is False
    assert "scheduler lock heartbeat unparsable" in caplog.text


def test_stop_scheduler_logs_when_release_fails(monkeypatch, caplog) -> None:
    from docker import scheduler as sched

    fake_db = MagicMock()
    fake_db.execute.side_effect = RuntimeError("delete failed")
    monkeypatch.setattr(sched, "_get_db", lambda: fake_db)
    monkeypatch.setattr(sched.scheduler, "shutdown", lambda wait=True: None)

    with caplog.at_level(logging.WARNING, logger="docker.scheduler"):
        sched.stop_scheduler()
    assert "release scheduler lock failed" in caplog.text
