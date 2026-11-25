"""A-17 回归：无 blocks 的纯文本渲染（Telegram 需 MarkdownV2 转义 + 补标题）。

B2（P1-3）补充：Markdown 渲染器（企微 Webhook / 钉钉 Webhook）在**无 blocks** 时
同样必须补标题——`task_progress` 等 body-only 事件此前在 Webhook 形态首行没有标题，
而 Telegram 早已覆盖（`renderer_telegram.py` 的 `_render_plain_text`）。
"""

from pilotstd.core.notification._builders_task_results import _build_task_progress_message
from pilotstd.core.notification.blocks import TextBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import (
    BlockRenderer,
    DesktopRenderer,
    MarkdownRenderer,
)
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


# ── B2 / P1-3：markdown 渲染器 body-only 补标题 ──────────────────────────────


def test_markdown_plain_text_prepends_title():
    """body-only 消息的 markdown 首行必须含标题（企微 Webhook 形态此前看不到标题）。"""
    msg = _build_task_progress_message(
        {"task_id": "t1", "task_name": "下载", "completed": 3, "total": 10, "percent": 30}
    )
    assert msg.blocks == [], "task_progress 构建器应仍是 body-only 消息（本用例前提）"
    out = MarkdownRenderer().render(msg)
    assert out.startswith(f"## {msg.title}\n\n"), f"首行未含标题：{out[:60]!r}"
    assert msg.body in out


def test_markdown_plain_text_uses_first_line_as_title():
    """判别力：`render().splitlines()[0]` 必须是标题行（对齐 TG 的补标题口径）。"""
    out = MarkdownRenderer().render(_msg())
    assert out.splitlines()[0] == "## A13"


def test_markdown_plain_text_title_only_when_body_empty():
    """只有标题、无正文时不得回退成裸标题（仍保留 markdown 标题语义）。"""
    msg = NotificationMessage(title="仅有标题", body="", event_type="test")
    assert MarkdownRenderer().render(msg) == "## 仅有标题"


def test_markdown_plain_text_without_title_is_verbatim():
    """标题为空时正文逐字输出（不凭空产生标题行）。"""
    msg = NotificationMessage(title="", body="paren test (2026-10-27).", event_type="test")
    assert MarkdownRenderer().render(msg) == "paren test (2026-10-27)."


def test_other_renderers_plain_text_stays_verbatim():
    """只为 markdown 渲染器加：基类与桌面渲染器的纯文本兜底保持逐字（不补标题）。"""
    body = "paren test (2026-10-27)."
    msg = NotificationMessage(title="A13", body=body, event_type="test")
    for renderer in (BlockRenderer(), DesktopRenderer()):
        assert renderer.render(msg) == body, f"{type(renderer).__name__} 的纯文本兜底被改动了"
