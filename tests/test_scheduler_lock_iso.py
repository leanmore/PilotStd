"""调度器锁：带偏移 ISO 心跳可解析，超时可接管。"""

from types import SimpleNamespace

import docker.scheduler as scheduler


class _DB:
    def __init__(self, heartbeat):
        self.heartbeat = heartbeat
        self.updated = None
        self.insert_attempts = 0

    def execute(self, sql, params=()):
        if "INSERT INTO scheduler_lock" in sql:
            self.insert_attempts += 1
            if self.insert_attempts == 1:
                raise RuntimeError("locked by other")
            self.updated = params
        return SimpleNamespace(rowcount=1)

    def fetchone(self, sql, params=()):
        return {"pid": 999, "heartbeat_at": self.heartbeat}


def test_stale_iso_heartbeat_can_be_taken_over(monkeypatch):
    db = _DB("2020-01-01T00:00:00+08:00")
    monkeypatch.setattr(scheduler, "_get_db", lambda: db)
    monkeypatch.setattr(scheduler, "_STALE_TIMEOUT", 60)
    assert scheduler._acquire_scheduler_lock() is True


def test_fresh_iso_heartbeat_blocks_second_worker(monkeypatch):
    db = _DB(scheduler.iso_now())
    monkeypatch.setattr(scheduler, "_get_db", lambda: db)
    monkeypatch.setattr(scheduler, "_STALE_TIMEOUT", 600)
    assert scheduler._acquire_scheduler_lock() is False
