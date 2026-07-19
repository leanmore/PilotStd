# tests/fixtures/notification_fixture.py
"""通知渠道 mock fixtures — 4 个渠道（telegram/feishu/dingtalk/wechat）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_channels() -> dict[str, MagicMock]:
    """返回 4 个通知渠道的 MagicMock 字典。

    用法:
        def test_notification_send(mock_channels):
            ch = mock_channels["telegram"]
            ch.send.return_value = True
    """
    channels = {
        "telegram": MagicMock(),
        "feishu": MagicMock(),
        "dingtalk": MagicMock(),
        "wechat": MagicMock(),
    }
    for name, ch in channels.items():
        ch.name = name
        ch.send.return_value = True
    return channels


@pytest.fixture
def patched_channels(mock_channels: dict[str, MagicMock]) -> dict[str, MagicMock]:  # type: ignore[misc]
    """patch 掉 4 个通知渠道的构造函数，返回 mock 实例。

    用法:
        def test_send_event(patched_channels):
            from pilotstd.core.notification import NotificationManager
            ...
    """
    channel_paths = {
        "telegram": "pilotstd.core.notification.channels.telegram.TelegramChannel",
        "feishu": "pilotstd.core.notification.channels.feishu.FeishuChannel",
        "dingtalk": "pilotstd.core.notification.channels.dingtalk.DingTalkChannel",
        "wechat": "pilotstd.core.notification.channels.wechat.WechatChannel",
    }
    patchers = {}
    for name, path in channel_paths.items():
        p = patch(path, return_value=mock_channels[name])
        p.start()
        patchers[name] = p

    yield mock_channels

    for p in patchers.values():
        p.stop()
