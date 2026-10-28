"""B1：/api/notification/test-event 走 dispatcher 路径（静音可验）。"""

from unittest.mock import MagicMock

import docker.api.notification as api


def _mgr(*, quiet: bool = False) -> MagicMock:
    mgr = MagicMock()
    mgr._channels = {"telegram": object()}
    mgr._is_quiet_hours.return_value = quiet
    return mgr


def test_warning_bypasses_quiet():
    mgr = _mgr(quiet=True)
    result = api.test_event(None, {"channel": "telegram", "level": "warning"}, nmgr=mgr)
    assert result == {"ok": True, "queued": False}
    msg, channels = mgr._do_send.call_args.args
    assert msg.level == "warning" and channels == ["telegram"]
    assert mgr._do_send.call_args.kwargs["bypass_aggregation"] is True


def test_info_in_quiet_is_queued():
    mgr = _mgr(quiet=True)
    result = api.test_event(None, {"channel": "telegram", "level": "info"}, nmgr=mgr)
    assert result == {"ok": True, "queued": True}
    msg = mgr._do_send.call_args.args[0]
    assert msg.level == "info"


def test_invalid_level_or_channel_rejected():
    mgr = _mgr()
    assert api.test_event(None, {"channel": "telegram", "level": "error"}, nmgr=mgr)["ok"] is False
    assert api.test_event(None, {"channel": "nope", "level": "info"}, nmgr=mgr)["ok"] is False
    mgr._do_send.assert_not_called()


def test_uninitialized_channel_rejected():
    mgr = _mgr()
    mgr._channels = {}
    result = api.test_event(None, {"channel": "telegram", "level": "info"}, nmgr=mgr)
    assert result == {"ok": False, "error": "channel not initialized"}
