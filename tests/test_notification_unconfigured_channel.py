"""未配置渠道不应写入 failed 日志。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from pilotstd.core.notification._dispatcher import send_now
from pilotstd.core.notification.channel import NotificationMessage


def test_unconfigured_channel_is_skipped_without_log() -> None:
    host = SimpleNamespace(_channels={}, _log=MagicMock())
    send_now(host, NotificationMessage(title="测试"), ["wechat"])
    host._log.assert_not_called()
