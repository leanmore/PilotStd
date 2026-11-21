"""D-2 缺口①补强回归：零渠道用户的事件不再静默丢弃（写 skipped 行，站内可见）。"""

from __future__ import annotations

from types import SimpleNamespace

from pilotstd.core.notification._dispatcher import send_event
from pilotstd.core.notification.channel import NotificationMessage


class _Cfg:
    def __init__(self, record: bool = True) -> None:
        self._record = record

    def get(self, key, default=None):
        if key == "notification.record_unconfigured_events":
            return self._record
        return default


def _host(record: bool = True):
    calls: list[tuple] = []

    def _log(event_type, channel, msg, status, error, sent_at):
        calls.append((event_type, channel, status, error))
        return len(calls)

    return SimpleNamespace(
        _local_sink=None,
        _enabled=True,
        _user_id=1,
        _policy=SimpleNamespace(get_channels_for_event=lambda uid, et, data: []),
        _cfg=_Cfg(record),
        _build_message=lambda et, data: NotificationMessage(title="t", body="b"),
        _log=_log,
        _do_send=lambda *a, **k: calls.append(("sent",)),
        ops=SimpleNamespace(apply_mapping=lambda *a, **k: None),
        _validate_message=lambda *a, **k: None,
        calls=calls,
    )


def test_zero_channel_writes_visible_skipped_row():
    host = _host()
    send_event(host, "download_failed", {"standard_number": "GB 1-2020"})
    rows = [c for c in host.calls if c[0] == "download_failed"]
    assert rows, "零渠道时必须留一行站内可见记录，而不是只打日志"
    event_type, channel, status, reason = rows[0]
    assert channel == "none"
    assert status == "skipped"
    assert reason


def test_switch_off_keeps_old_behavior():
    host = _host(record=False)
    send_event(host, "download_failed", {})
    assert not [c for c in host.calls if c[0] == "download_failed"]
