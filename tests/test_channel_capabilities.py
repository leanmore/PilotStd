"""阶段 B（B1）：渠道能力声明与改写句柄抽象。

设计依据：docs/plans/notification-system-design/02-framework-update.md §2.3
（"基础先行：先做渠道无关的公共能力（改写句柄抽象、回调端点骨架、验签骨架）"）
与 01-channel-capabilities.md §四 结论 3（四家编辑锚点不统一）。
"""

import json
from unittest.mock import patch

from pilotstd.core.notification.channel_spec import CHANNEL_SPECS, channel_class
from pilotstd.core.notification.channels.telegram import TelegramChannel
from pilotstd.core.notification.interaction import (
    ANCHOR_MESSAGE_ID,
    ANCHOR_OUT_TRACK_ID,
    ChannelCapabilities,
    MessageHandle,
)


def _telegram() -> TelegramChannel:
    return TelegramChannel(bot_token="tok", chat_id="chat-1")


class _Resp:
    """真实上下文管理器替身（`with` 按类型查找 `__enter__`，MagicMock 实例级赋值无效）。"""

    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


class TestCapabilityDeclarations:
    """能力自述必须与**证据**一致：能编辑的只有 TG；企微连回调都不启用。"""

    def test_every_spec_channel_exposes_capabilities(self):
        for spec in CHANNEL_SPECS:
            cls = channel_class(spec)
            self_caps = cls.__dict__.get("capabilities")
            assert self_caps is not None, f"{spec.name} 未声明 capabilities"

    def test_declarations_match_evidence(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        from pilotstd.core.notification.channels.wechat import WechatChannel

        cases = [
            (TelegramChannel(bot_token="t", chat_id="c"), True, True),
            (DingTalkChannel(webhook_url="http://x"), True, False),
            (FeishuChannel(webhook_url="http://x"), True, False),
            (WechatChannel(webhook_url="http://x"), False, False),
        ]
        for channel, callback, edit in cases:
            caps = channel.capabilities
            assert caps.supports_callback is callback, channel.name
            assert caps.supports_edit is edit, channel.name

    def test_edit_anchor_only_where_editing_supported(self):
        assert _telegram().capabilities.edit_anchor == ANCHOR_MESSAGE_ID
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        # 钉钉锚点存在（outTrackId）但编辑能力未启用 ⇒ 不声明 edit_anchor，
        # 避免调用方误以为可编辑
        assert DingTalkChannel(webhook_url="http://x").capabilities.edit_anchor == ""
        assert ANCHOR_OUT_TRACK_ID  # 闭集常量存在，供后续补证后启用

    def test_capability_note_present_where_missing(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        from pilotstd.core.notification.channels.wechat import WechatChannel

        for channel in (
            DingTalkChannel(webhook_url="http://x"),
            FeishuChannel(webhook_url="http://x"),
            WechatChannel(webhook_url="http://x"),
        ):
            assert channel.capabilities.note_key, channel.name


class TestEditHandle:
    """改写句柄：渠道无关的 `(channel, anchor, value)`。"""

    def test_handle_is_channel_agnostic(self):
        tg = MessageHandle("telegram", ANCHOR_MESSAGE_ID, "42")
        dd = MessageHandle("dingtalk", ANCHOR_OUT_TRACK_ID, "track-1")
        assert (tg.channel, tg.value) == ("telegram", "42")
        assert dd.anchor == ANCHOR_OUT_TRACK_ID

    def test_default_channel_refuses_edit(self):
        """基类默认实现：返回 False 且写 last_error（失败必须可见）。"""
        from pilotstd.core.notification.channels.base import NotificationChannel

        class _Stub(NotificationChannel):
            def send(self, message):  # type: ignore[no-untyped-def]
                return True

            def test(self) -> bool:
                return True

            @property
            def name(self) -> str:
                return "stub"

            def get_config_schema(self) -> dict:
                return {}

        stub = _Stub()
        assert stub.capabilities == ChannelCapabilities()
        assert stub.edit_message(MessageHandle("stub", ANCHOR_MESSAGE_ID, "1"), None) is False
        assert stub.last_error


class TestTelegramEdit:
    """TG 编辑：成功 / 平台失败 / 锚点不符 三种路径。"""

    def _msg(self):
        from pilotstd.core.notification.channel import NotificationMessage

        return NotificationMessage(title="标题", body="正文")

    def test_edit_success(self):
        ch = _telegram()
        with patch(
            "pilotstd.core.notification.channels.telegram.urlopen",
            return_value=_Resp({"ok": True, "result": {}}),
        ):
            assert ch.edit_message(MessageHandle("telegram", ANCHOR_MESSAGE_ID, "42"), self._msg()) is True
        assert ch.last_error == ""

    def test_edit_platform_failure_records_error(self):
        ch = _telegram()
        with patch(
            "pilotstd.core.notification.channels.telegram.urlopen",
            return_value=_Resp({"ok": False, "description": "message is not modified"}),
        ):
            assert ch.edit_message(MessageHandle("telegram", ANCHOR_MESSAGE_ID, "42"), self._msg()) is False
        assert "message is not modified" in ch.last_error

    def test_edit_wrong_anchor_refused_without_network(self):
        ch = _telegram()
        with patch("pilotstd.core.notification.channels.telegram.urlopen") as mock_open:
            assert ch.edit_message(MessageHandle("telegram", ANCHOR_OUT_TRACK_ID, "x"), self._msg()) is False
        mock_open.assert_not_called()
        assert "锚点" in ch.last_error
