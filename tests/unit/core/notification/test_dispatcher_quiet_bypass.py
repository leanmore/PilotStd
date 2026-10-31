"""N1 裁决回归：静音时段内，警告/错误必须绕过静音直接发送。

背景：2026-10-24 裁决「警告绕过静默」。修复前 `do_send` 只看"是否静音"，
不看消息级别，导致警告也被写入 `notification_queue` 延后补发——等于没告警。
"""

import unittest

from pilotstd.core.notification._dispatcher import do_send
from pilotstd.core.notification.channel import NotificationMessage


class _Host:
    """最小宿主替身：只实现 do_send 实际用到的三个入口。"""

    aggregator = None

    def __init__(self, quiet: bool) -> None:
        self._quiet = quiet
        self.queued: list[str] = []
        self.sent: list[str] = []

    def _is_quiet_hours(self, user_id: int | None = None) -> bool:
        return self._quiet

    def _enqueue_notification(self, msg: NotificationMessage, channels: list[str]) -> None:
        self.queued.append(msg.level)

    def _send_now(self, msg: NotificationMessage, channels: list[str]) -> None:
        self.sent.append(msg.level)


def _msg(level: str) -> NotificationMessage:
    return NotificationMessage(title="t", level=level, event_type="auto_backup")


class TestQuietBypass(unittest.TestCase):
    """静音期按级别分流。"""

    def test_warning_bypasses_quiet(self) -> None:
        host = _Host(quiet=True)
        do_send(host, _msg("warning"), [], bypass_aggregation=True)
        self.assertEqual(host.sent, ["warning"])
        self.assertEqual(host.queued, [])

    def test_error_bypasses_quiet(self) -> None:
        host = _Host(quiet=True)
        do_send(host, _msg("error"), [], bypass_aggregation=True)
        self.assertEqual(host.sent, ["error"])
        self.assertEqual(host.queued, [])

    def test_info_still_queued(self) -> None:
        host = _Host(quiet=True)
        do_send(host, _msg("info"), [], bypass_aggregation=True)
        self.assertEqual(host.queued, ["info"])
        self.assertEqual(host.sent, [])

    def test_info_sent_when_not_quiet(self) -> None:
        host = _Host(quiet=False)
        do_send(host, _msg("info"), [], bypass_aggregation=True)
        self.assertEqual(host.sent, ["info"])
        self.assertEqual(host.queued, [])


if __name__ == "__main__":
    unittest.main()
