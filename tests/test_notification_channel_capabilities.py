"""D-2 模块化缺口回归：能力矩阵 + 菜单工厂注册表。"""

from __future__ import annotations

from pilotstd.core.notification.interaction import channel_capabilities
from pilotstd.core.notification.menu.clients import (
    DingtalkMenuClient,
    FeishuMenuClient,
    TelegramCommandClient,
    WecomMenuClient,
)
from pilotstd.core.notification.menu.service import MENU_CHANNELS, MENU_CLIENT_FACTORIES


def test_capability_matrix_matches_renderers():
    """能力按“渲染器实际能做什么”声明，不按渠道名臆测。"""
    wechat = channel_capabilities("wechat")
    assert wechat.supports_mention is True       # touser=@all
    assert wechat.supports_buttons is False      # news_notice 卡片不产按钮
    assert wechat.supports_image is False        # 通知链路不发图

    feishu = channel_capabilities("feishu")
    assert feishu.supports_buttons is True       # 卡片 action 按钮
    assert feishu.supports_edit is True

    telegram = channel_capabilities("telegram")
    assert telegram.supports_buttons is True     # inline_keyboard

    dingtalk = channel_capabilities("dingtalk")
    assert dingtalk.supports_buttons is False    # 模板参数只有 title/content/level
    assert dingtalk.supports_callback is False


def test_unknown_channel_is_all_false():
    cap = channel_capabilities("weibo")
    assert not (cap.supports_image or cap.supports_mention or cap.supports_buttons or cap.supports_callback)


def test_menu_factories_cover_all_channels():
    """注册表键必须与渠道元组一致 —— 加渠道时只改一处，漏登记会在这里红。"""
    assert set(MENU_CLIENT_FACTORIES) == set(MENU_CHANNELS)


def test_menu_factories_resolve_expected_clients():
    class _Cfg:
        def get(self, key, default=None):
            return {}

    expected = {
        "wechat": WecomMenuClient,
        "feishu": FeishuMenuClient,
        "telegram": TelegramCommandClient,
        "dingtalk": DingtalkMenuClient,
    }
    for channel, cls in expected.items():
        client = MENU_CLIENT_FACTORIES[channel]({}, _Cfg(), None)
        assert isinstance(client, cls), channel
