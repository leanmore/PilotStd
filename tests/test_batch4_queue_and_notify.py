"""批次四：任务队列兜底 handler + 通知归属（后台任务 context / 按钮 token）。"""

import time
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from pilotstd.core.db import Database
from pilotstd.task.models import TaskStatus, TaskType
from pilotstd.task.queue import TaskQueue


@pytest.fixture()
def db(tmp_path):
    return Database(str(tmp_path / "t.db"))


def test_task_queue_unimplemented_fails_fast(db):
    """没有真实 handler 的任务必须快速进入 FAILED，而不是永久 pending。"""
    queue = TaskQueue(db)
    task = queue.enqueue(TaskType.SCAN, total_items=1)
    queue.start(task)

    deadline = time.time() + 5
    while time.time() < deadline:
        current = queue.get(task.task_id)
        if current and current.status in (TaskStatus.FAILED, TaskStatus.COMPLETED):
            break
        time.sleep(0.05)

    current = queue.get(task.task_id)
    assert current.status is TaskStatus.FAILED
    assert "尚未实现" in current.error_log


def test_task_queue_real_handler_overrides_default(db):
    queue = TaskQueue(db)
    done = MagicMock()
    done.return_value = None
    queue.register_handler(TaskType.QUERY, done)

    task = queue.enqueue(TaskType.QUERY, total_items=1)
    queue.start(task)
    deadline = time.time() + 5
    while time.time() < deadline:
        current = queue.get(task.task_id)
        if current and current.status is TaskStatus.COMPLETED:
            break
        time.sleep(0.05)

    assert done.called
    assert queue.get(task.task_id).status is TaskStatus.COMPLETED


def test_favorite_download_notifies_with_user_context(monkeypatch):
    from pilotstd.tasks import favorite_download as fd

    monkeypatch.setattr(fd, "_fetch_std_meta", lambda n: {"standard_name": "名", "standard_type": "NationalStd"})
    mgr = MagicMock()
    monkeypatch.setattr("pilotstd.manager.facade.StandardManager", lambda: mgr)

    fd._notify_download_complete(3, "GB 1-2020", 7, "/standards/x.pdf")

    kwargs = mgr.notification_mgr.send_event.call_args.kwargs
    assert kwargs["context"].scope == "user"
    assert kwargs["context"].user_id == 3


def test_date_reminder_uses_user_context(db):
    from pilotstd.tasks.date_reminder import _process_record

    today = date.today()
    due = (today + timedelta(days=30)).isoformat()
    db.execute("INSERT INTO users (id, username, password_hash, salt) VALUES (1,'u1','x','s')")
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, standard_number, std_name, implement_date,"
        " status, fetched_at) VALUES ('announcement_gb','p','GB 1-2020','名',?,'approved','2026-01-01')",
        (due,),
    )
    rec_id = db.fetchone("SELECT id FROM announcement_record")["id"]
    db.execute("INSERT INTO user_favorites (user_id, record_id) VALUES (1, ?)", (rec_id,))
    fav_id = db.fetchone("SELECT id FROM user_favorites")["id"]
    db.execute(
        "INSERT INTO favorite_downloads (favorite_id, record_id, user_id, status)"
        " VALUES (?, ?, 1, 'done')",
        (fav_id, rec_id),
    )

    notif = MagicMock()
    stats = {"sent": 0, "skipped": 0}
    _process_record(
        {
            "id": rec_id,
            "remind_type": "implement",
            "implement_date": due,
            "standard_number": "GB 1-2020",
            "std_name": "名",
        },
        today,
        db,
        notif,
        stats,
    )

    assert stats["sent"] == 1
    ctx = notif.send_event.call_args.kwargs["context"]
    assert ctx.scope == "user" and ctx.user_id == 1


def test_dispatcher_mints_token_for_delivery_user():
    """按钮 token 必须用 delivery_user_id，而不是 manager 的默认 user_id。"""
    from pilotstd.core.notification._dispatcher import send_now
    from pilotstd.core.notification.channel import NotificationMessage

    class Ops:
        def __init__(self):
            self.updated = []

        def update_log_fields(self, log_id, **fields):
            self.updated.append((log_id, fields))

    class Channel:
        last_error = ""

        def send(self, msg):
            return True

    class Host:
        _user_id = 1
        _channels = {"telegram": Channel()}
        _cfg = None

        def __init__(self):
            self.ops = Ops()

        def _log(self, event_type, channel, msg, status, error, sent_at):
            return 42

        def _record_delivery(self, channel, ok):
            return None

        def channels_for(self, uid):
            return self._channels

    host = Host()
    msg = NotificationMessage(
        title="t",
        body="b",
        event_type="favorite_created",
        user_id=3,
        delivery_user_id=3,
        actions=[object()],
    )
    send_now(host, msg, ["telegram"])

    callback_updates = [f for _, f in host.ops.updated if "callback_data" in f]
    assert callback_updates and callback_updates[0]["callback_data"] == "42:3"
