"""调度器辅助函数：备份清理、任务注册、错误监听。"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import docker.scheduler as s


def test_prune_old_backups_keeps_newest(tmp_path):
    for i in range(5):
        p = tmp_path / f"pilotstd_{i}.bak"
        p.write_bytes(b"x")
        os.utime(p, (1000 + i, 1000 + i))
    removed = s._prune_old_backups(str(tmp_path), keep=2)
    assert len(removed) == 3
    remain = sorted(os.listdir(tmp_path))
    assert len(remain) == 2
    assert "pilotstd_3.bak" in remain and "pilotstd_4.bak" in remain


def test_add_interval_and_cron_jobs(monkeypatch):
    fake_scheduler = MagicMock()
    monkeypatch.setattr(s, "scheduler", fake_scheduler)
    s._job_funcs["unit_interval"] = lambda: None
    s._job_funcs["unit_cron"] = lambda: None
    s._add_interval_job("unit_interval", 30)
    s._add_cron_job("unit_cron", "0 3 * * *")
    assert fake_scheduler.add_job.call_count == 2


def test_register_job_wraps_announce_in_thread(monkeypatch):
    called = []
    monkeypatch.setattr(s, "capture_task_error", lambda job_id: (lambda fn: fn))
    s.register_job_func("announce_test", lambda: called.append(1))
    s._job_funcs["announce_test"]()
    import time

    time.sleep(0.1)
    assert called == [1]


def test_retention_cleanup_runs(monkeypatch):
    db = MagicMock()
    db.execute.return_value.rowcount = 1
    monkeypatch.setattr(s, "_get_db", lambda: db)
    monkeypatch.setattr(s, "ConfigManager", lambda: SimpleNamespace(get=lambda k, d=0: d))
    s._cleanup_retention()
    assert db.execute.call_count == 2


def test_release_suppressed_notifications(monkeypatch):
    mgr = SimpleNamespace(release_suppressed_notifications=lambda: 3)
    s._release_suppressed_notifications(mgr)


def test_backup_database_success(monkeypatch, tmp_path):
    db = MagicMock()
    db.path = str(tmp_path / "pilotstd.db")
    db.backup.side_effect = lambda path: path
    monkeypatch.setattr(s, "_get_db", lambda: db)
    notified = []
    mgr = SimpleNamespace(send_event=lambda event, data: notified.append(event))
    s._backup_database(mgr)
    assert notified == ["auto_backup"]


def test_cleanup_notification_logs(monkeypatch):
    mgr = SimpleNamespace(ops=SimpleNamespace(cleanup_logs=lambda days: 2))
    monkeypatch.setattr(s, "ConfigManager", lambda: SimpleNamespace(get=lambda k, d=0: d))
    s._cleanup_notification_logs(mgr)



def test_date_reminder_wrapper(monkeypatch):
    calls = []
    monkeypatch.setattr(s, "run_date_reminder", lambda notification_mgr=None: calls.append(notification_mgr))
    s._date_reminder_wrapper(SimpleNamespace())
    assert len(calls) == 1


def test_update_job_branches(monkeypatch):
    fake = MagicMock()
    fake.get_job.return_value = object()
    monkeypatch.setattr(s, "scheduler", fake)
    s.update_job("j", "0 1 * * *", True)
    s.update_job("j", "0 1 * * *", True)
    s.update_job("j", "0 1 * * *", False)
    assert fake.reschedule_job.call_count >= 1
    assert fake.remove_job.call_count >= 1


def test_stop_scheduler_releases_lock(monkeypatch):
    fake = MagicMock()
    db = MagicMock()
    monkeypatch.setattr(s, "scheduler", fake)
    monkeypatch.setattr(s, "_get_db", lambda: db)
    s.stop_scheduler()
    fake.shutdown.assert_called_once()
    assert db.execute.called


def test_backup_failure_notifies(monkeypatch, tmp_path):
    db = MagicMock()
    db.path = str(tmp_path / "pilotstd.db")
    db.backup.return_value = None
    monkeypatch.setattr(s, "_get_db", lambda: db)
    events = []
    mgr = SimpleNamespace(send_event=lambda event, data: events.append(data))
    s._backup_database(mgr)
    assert events and events[0]["success"] is False

