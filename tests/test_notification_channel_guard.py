"""通知渠道初始化/退避参数回归：未配置渠道不应进入发送队列。"""

from unittest.mock import MagicMock

from pilotstd.core.notification.manager import NotificationManager


def test_parse_retry_after_accepts_numeric_value() -> None:
    from pilotstd.core.notification.channels.base import parse_retry_after

    assert parse_retry_after(3.5) is None  # type: ignore[arg-type]
    assert parse_retry_after("retry after 3.5") == 3.5


def test_init_channels_skips_unconfigured_webhook_channel() -> None:
    mgr = NotificationManager.__new__(NotificationManager)
    mgr._user_id = 1
    mgr._channels = {}
    mgr._cred_helper = MagicMock()
    mgr._cred_helper.get_all.return_value = {"wechat": {"enabled": True}}
    mgr._init_channels()
    assert "wechat" not in mgr._channels
