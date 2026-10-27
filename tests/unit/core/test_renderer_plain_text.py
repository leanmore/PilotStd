"""A-17 回归：无 blocks 的纯文本渲染（Telegram 需 MarkdownV2 转义 + 补标题）。"""

from pilotstd.core.notification.blocks import TextBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import MarkdownRenderer
from pilotstd.core.notification.renderer_telegram import TelegramRenderer


def _msg(**kw) -> NotificationMessage:
    return NotificationMessage(title="A13", body="paren test (2026-10-27).", event_type="test", **kw)


def test_telegram_plain_text_is_escaped_and_has_title():
    out = TelegramRenderer().render(_msg())
    assert out.startswith("*A13*")
    assert "\\(" in out and "\\)" in out and "\\." in out
    # 原文的括号/点不得以未转义形态出现
    assert "(2026-10-27)." not in out


def test_telegram_with_blocks_uses_block_path_not_plain_hook():
    msg = _msg(blocks=[TextBlock("hello")])
    out = TelegramRenderer().render(msg)
    # 带 blocks 时正文不参与渲染，标题走块路径（加粗）
    assert out.startswith("*A13*")
    assert "hello" in out
    assert "paren test" not in out


def test_non_telegram_renderer_plain_text_is_verbatim():
    """其它渠道默认钩子不改动正文：MarkdownRenderer 的纯文本兜底保持逐字。"""
    body = "paren test (2026-10-27)."
    msg = NotificationMessage(title="A13", body=body, event_type="test")
    assert MarkdownRenderer().render(msg) == body
