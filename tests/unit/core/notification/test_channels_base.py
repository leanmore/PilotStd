# tests/unit/core/notification/test_channels_base.py
"""v1.1 R2 Step 3：渠道抽象基类契约测试。

验证：
- 抽象基类不可实例化（未实现 send/test/name/get_config_schema）
- 4 个渠道均继承新基类并实现全部抽象成员
- get_config_schema 返回结构化字段定义（type/label/required）
- test() 通过 send() 发送测试消息并返回其结果
"""

from __future__ import annotations

import pytest

from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.channels.base import NotificationChannel
from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
from pilotstd.core.notification.channels.feishu import FeishuChannel
from pilotstd.core.notification.channels.telegram import TelegramChannel
from pilotstd.core.notification.channels.wechat import WechatChannel
from pilotstd.i18n import t


def test_abstract_base_cannot_instantiate() -> None:
    """抽象基类缺 send/test/name/get_config_schema → 实例化抛 TypeError。"""
    with pytest.raises(TypeError):
        NotificationChannel()  # type: ignore[abstract]


@pytest.mark.parametrize(
    "channel_cls,expected_name,init_args",
    [
        (TelegramChannel, "telegram", ("tok", "123")),
        (WechatChannel, "wechat", ("http://hook",)),
        (DingTalkChannel, "dingtalk", ("http://hook",)),
        (FeishuChannel, "feishu", ("http://hook",)),
    ],
)
def test_channel_inherits_new_base_and_implements_contract(
    channel_cls, expected_name: str, init_args: tuple
) -> None:
    """4 渠道统一继承 channels.base.NotificationChannel 并实现全部抽象成员。"""
    ch = channel_cls(*init_args)
    assert isinstance(ch, NotificationChannel)
    # name 属性
    assert ch.name == expected_name
    # get_config_schema：结构化字段定义
    schema = ch.get_config_schema()
    assert isinstance(schema, dict)
    assert len(schema) > 0
    for field, meta in schema.items():
        assert field
        assert "type" in meta, f"{field} 缺 type"
        assert "label" in meta, f"{field} 缺 label"
        assert "required" in meta, f"{field} 缺 required"
    # validate_config 静态方法可用（基类默认 True，子类可覆盖）
    assert NotificationChannel.validate_config({}) is True


@pytest.mark.parametrize(
    "channel_cls,init_args",
    [
        (TelegramChannel, ("tok", "123")),
        (WechatChannel, ("http://hook",)),
        (DingTalkChannel, ("http://hook",)),
        (FeishuChannel, ("http://hook",)),
    ],
)
def test_test_method_sends_via_send(channel_cls, init_args: tuple, monkeypatch) -> None:
    """test() 通过 send() 发送一条测试消息并返回其发送结果。"""
    ch = channel_cls(*init_args)
    sent: list[NotificationMessage] = []
    monkeypatch.setattr(ch, "send", lambda m: (sent.append(m), True)[1])
    assert ch.test() is True
    assert len(sent) == 1
    assert sent[0].title == t("notification.channel.test.title")
    assert sent[0].event_type == ""  # 测试消息不带事件类型（非业务通知）


def test_send_failure_populates_last_error() -> None:
    """send 失败路径填充 last_error（契约：失败必须可诊断）。"""
    ch = TelegramChannel("", "")  # 未配置 → send 直接失败
    assert ch.send(NotificationMessage(title="T", body="b")) is False
    assert ch.last_error  # 非空
