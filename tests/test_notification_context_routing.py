"""A-21 3b-4：system 全 admin 投递与按用户渠道缓存。"""

from unittest.mock import MagicMock, patch

from pilotstd.core.notification.context import NotificationContext
from pilotstd.core.notification.manager import NotificationManager


def _mgr(admin_ids):
    m = object.__new__(NotificationManager)
    m._user_id = 9
    m._db = MagicMock()
    m._db.fetchall.return_value = [{"id": i} for i in admin_ids]
    m._system_enabled = True
    return m


def test_system_fans_out_to_all_admins():
    m = _mgr([1, 2])
    with patch("pilotstd.core.notification.manager._dispatcher.send_event") as send:
        NotificationManager.send_event(
            m, "scan_complete", {}, context=NotificationContext(scope="system")
        )
    assert send.call_count == 2
    delivered = [c.kwargs["delivery_user_id"] for c in send.call_args_list]
    assert delivered == [1, 2]
    assert all(c.args[5].scope == "system" for c in send.call_args_list)


def test_user_scope_single_delivery():
    m = _mgr([1, 2])
    with patch("pilotstd.core.notification.manager._dispatcher.send_event") as send:
        NotificationManager.send_event(
            m, "scan_complete", {}, context=NotificationContext(scope="user", user_id=2)
        )
    assert send.call_count == 1
    assert send.call_args.kwargs["delivery_user_id"] == 2


def test_channels_for_caches_per_user():
    m = object.__new__(NotificationManager)
    m._user_id = 1
    m._channels = {"a": object()}
    m._channel_cache = {1: m._channels}
    m._build_channels = MagicMock(return_value={"b": object()})
    assert m.channels_for(2) == m._build_channels.return_value
    assert m.channels_for(2) is m._build_channels.return_value
    m._build_channels.assert_called_once_with(2)
    m.invalidate_channels(2)
    assert 2 not in m._channel_cache
