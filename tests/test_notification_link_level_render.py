"""D-2 缺口②③回归：message.link 渲染 + 级别跨渠道可见。"""

from __future__ import annotations

from pilotstd.core.notification._links import absolute_link, absolutize_message_link
from pilotstd.core.notification.blocks import TextBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import (
    DingTalkCardRenderer,
    FeishuCardRenderer,
    MarkdownRenderer,
)
from pilotstd.core.notification.renderer_base import detail_link_line, level_prefix


class _Cfg:
    def __init__(self, base: str = "") -> None:
        self._base = base

    def get(self, key: str, default=None):
        if key == "notification.web_base_url":
            return self._base
        return default


def _msg(level: str = "info", link: str | None = "/standards/GB 1-2020") -> NotificationMessage:
    return NotificationMessage(
        title="标准状态变更",
        body="GB 1-2020 现行 → 废止",
        level=level,
        blocks=[TextBlock(text="GB 1-2020 现行 → 废止")],
        link=link,
    )


def test_absolute_link_rules():
    assert absolute_link("https://x.example", "/standards/1") == "https://x.example/standards/1"
    assert absolute_link("https://x.example/", "standards/1") == "https://x.example/standards/1"
    assert absolute_link("", "/standards/1") == ""          # 无基址：宁可不给
    assert absolute_link("https://x.example", "https://y.example/z") == "https://y.example/z"


def test_absolutize_message_link_uses_config():
    m = absolutize_message_link(_msg(), _Cfg("https://pilot.example"))
    assert m.link == "https://pilot.example/standards/GB 1-2020"
    # 未配置基址：链接被清空（聊天里不出现坏链）
    m2 = absolutize_message_link(_msg(), _Cfg(""))
    assert m2.link is None


def test_level_prefix_only_for_warning_and_error():
    assert level_prefix("info") == ""
    assert "警告" in level_prefix("warning")
    assert "错误" in level_prefix("error")


def test_markdown_render_includes_prefix_and_link():
    m = _msg(level="warning", link="https://pilot.example/standards/GB 1-2020")
    text = MarkdownRenderer().render(m)
    assert "警告" in text
    assert "https://pilot.example/standards/GB 1-2020" in text


def test_feishu_card_includes_link_element_and_title_prefix():
    m = _msg(level="error", link="https://pilot.example/standards/GB 1-2020")
    card = FeishuCardRenderer().render(m)
    assert "错误" in card["header"]["title"]["content"]
    joined = str(card["elements"])
    assert "https://pilot.example/standards/GB 1-2020" in joined


def test_dingtalk_card_content_includes_link_and_prefix():
    m = _msg(level="warning", link="https://pilot.example/standards/GB 1-2020")
    card = DingTalkCardRenderer().render_card(m)
    content = card["cardParamMap"]["content"]
    assert "警告" in content
    assert "https://pilot.example/standards/GB 1-2020" in content


def test_detail_line_empty_without_link():
    assert detail_link_line(_msg(link=None)) == ""
