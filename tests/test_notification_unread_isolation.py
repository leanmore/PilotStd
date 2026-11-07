"""通知未读数 / 全部已读必须与日志列表同口径（2026-11-07）。"""

from unittest.mock import MagicMock

import docker.api.notification_logs as logs_api
from pilotstd.core.notification._manager_ops import NotificationOps


def _ops() -> NotificationOps:
    mgr = MagicMock()
    mgr._db = MagicMock()
    return NotificationOps(mgr)


def test_unread_count_without_user_is_global():
    ops = _ops()
    ops._mgr._db.fetchone.return_value = {"cnt": 5}

    assert ops.get_unread_count() == 5
    sql = ops._mgr._db.fetchone.call_args.args[0]
    assert "user_id" not in sql


def test_unread_count_with_user_filters_user():
    ops = _ops()
    ops._mgr._db.fetchone.return_value = {"cnt": 3}

    assert ops.get_unread_count(7) == 3
    sql, params = ops._mgr._db.fetchone.call_args.args
    assert "user_id = ?" in sql
    assert params == (7,)


def test_mark_ids_with_user_filters_user():
    ops = _ops()
    ops._mgr._db.execute.return_value.rowcount = 1

    assert ops.mark_logs_read([1, 2], user_id=7) == 2
    calls = ops._mgr._db.execute.call_args_list
    assert len(calls) == 2
    for call in calls:
        sql, params = call.args
        assert "user_id = ?" in sql
        assert params[1] == 7


def test_mark_all_with_user_only_touches_user():
    ops = _ops()

    assert ops.mark_logs_read(None, user_id=7) == 0
    sql, params = ops._mgr._db.execute.call_args.args
    assert "user_id = ?" in sql
    assert params == (7,)


def test_api_unread_count_uses_current_user():
    nmgr = MagicMock()
    nmgr.ops.get_unread_count.return_value = 3

    assert logs_api.get_unread_count(request=MagicMock(), nmgr=nmgr, current_user=7) == {"count": 3}
    nmgr.ops.get_unread_count.assert_called_once_with(7, include_system=False)


def test_api_mark_read_uses_current_user():
    nmgr = MagicMock()
    nmgr.ops.get_logs.return_value = {"items": [{"id": 1}]}
    nmgr.ops.mark_logs_read.return_value = 1

    result = logs_api.mark_notification_read(
        body=logs_api.MarkReadRequest(id=1),
        request=MagicMock(),
        nmgr=nmgr,
        current_user=7,
    )

    assert result["ok"] is True
    assert result["count"] == 1
    nmgr.ops.get_logs.assert_called_once_with(
        page=1, size=1, start_date=None, end_date=None, user_id=7, include_system=False
    )
    nmgr.ops.mark_logs_read.assert_called_once_with([1], user_id=7, include_system=False)

def test_get_logs_include_system_for_admin():
    ops = _ops()
    ops._mgr._db.fetchone.return_value = {"cnt": 2}
    ops._mgr._db.fetchall.return_value = []
    result = ops.get_logs(user_id=7, include_system=True)
    assert result["total"] == 2
    sql, params = ops._mgr._db.fetchone.call_args.args
    assert "user_id = 0 OR user_id IS NULL" in sql
    assert params == (7,)


def test_unread_count_include_system_for_admin():
    ops = _ops()
    ops._mgr._db.fetchone.return_value = {"cnt": 9}
    assert ops.get_unread_count(7, include_system=True) == 9
    sql, params = ops._mgr._db.fetchone.call_args.args
    assert "user_id = 0 OR user_id IS NULL" in sql
    assert params == (7,)


def test_mark_all_include_system_for_admin():
    ops = _ops()
    assert ops.mark_logs_read(None, user_id=7, include_system=True) == 0
    sql, params = ops._mgr._db.execute.call_args.args
    assert "user_id = 0 OR user_id IS NULL" in sql
    assert params == (7,)
