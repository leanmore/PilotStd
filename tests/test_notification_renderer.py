"""core/notification/renderer.py 补测 — BlockRenderer + 4 个子类全覆盖。"""
import pytest
from pilotstd.core.notification.blocks import (
    TextBlock, KeyValueBlock, StatusChangeBlock, ListBlock,
)
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import (
    BlockRenderer, TelegramRenderer, MarkdownRenderer,
    FeishuCardRenderer, DesktopRenderer,
)


def make_msg(title="Test", body="fallback", blocks=None):
    msg = NotificationMessage(title=title, body=body)
    if blocks is not None:
        msg.blocks = blocks
    return msg


class TestBlockRenderer:
    def test_render_fallback_body_when_no_blocks(self):
        r = BlockRenderer().render(make_msg(title="T", body="hello"))
        assert r == "hello"

    def test_render_empty_blocks_empty_body(self):
        r = BlockRenderer().render(make_msg(title="", body="", blocks=[]))
        assert r == ""

    def test_render_text_block(self):
        b = TextBlock(text="plain text")
        r = BlockRenderer().render(make_msg(blocks=[b]))
        assert "plain text" in r

    def test_render_key_value_block(self):
        b = KeyValueBlock(key="Status", value="OK")
        r = BlockRenderer().render(make_msg(blocks=[b]))
        assert "Status: OK" in r

    def test_render_status_change_block(self):
        b = StatusChangeBlock(label="State", old_value="old", new_value="new")
        r = BlockRenderer().render(make_msg(blocks=[b]))
        assert "old" in r and "new" in r

    def test_render_list_block(self):
        b = ListBlock(title="Items", items=[{"a": "1"}, {"b": "2"}])
        r = BlockRenderer().render(make_msg(blocks=[b]))
        assert "Items" in r

    def test_render_list_with_detail_url(self):
        b = ListBlock(title="L", items=[{"k": "v"}], detail_url="http://x.com")
        r = BlockRenderer().render(make_msg(blocks=[b]))
        assert "http://x.com" in r

    def test_render_list_with_explicit_total(self):
        b = ListBlock(title="L", items=[{"a": "1"}], total=99)
        r = BlockRenderer().render(make_msg(blocks=[b]))
        assert "共 99 条" in r


class TestTelegramRenderer:
    def test_render_title_bold_with_block(self):
        b = TextBlock(text="msg")
        r = TelegramRenderer().render(make_msg(title="Alert", blocks=[b]))
        assert "*Alert*" in r

    def test_escape_special_chars(self):
        r = TelegramRenderer()
        assert r._escape("a_b") == r"a\_b"

    def test_render_list_number_bold(self):
        b = ListBlock(title="R", items=[{"number": "GB/T 1", "status": "现行"}])
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        assert "*GB/T 1*" in r


class TestMarkdownRenderer:
    def test_render_title_heading(self):
        b = TextBlock(text="content")
        r = MarkdownRenderer().render(make_msg(title="H", blocks=[b]))
        assert "## H" in r

    def test_render_list_with_url(self):
        b = ListBlock(title="L", items=[{"k": "v"}], detail_url="http://x.com")
        r = MarkdownRenderer().render(make_msg(blocks=[b]))
        assert "http://x.com" in r


class TestFeishuCardRenderer:
    def test_render_returns_dict(self):
        b = TextBlock(text="hi")
        r = FeishuCardRenderer().render(make_msg(blocks=[b]))
        assert isinstance(r, dict)
        assert "elements" in r

    def test_render_key_value_in_card(self):
        b = KeyValueBlock(key="K", value="V")
        r = FeishuCardRenderer().render(make_msg(blocks=[b]))
        assert r["elements"][0]["tag"] == "markdown"

    def test_render_status_change(self):
        b = StatusChangeBlock(label="State", old_value="A", new_value="B")
        r = FeishuCardRenderer().render(make_msg(blocks=[b]))
        assert len(r["elements"]) >= 1

    def test_render_list_as_card(self):
        b = ListBlock(title="List", items=[{"k": "v"}], detail_url="http://u.com")
        r = FeishuCardRenderer().render(make_msg(blocks=[b]))
        assert isinstance(r["elements"], list)


class TestDesktopRenderer:
    def test_render_text_block(self):
        b = TextBlock(text="desktop msg")
        r = DesktopRenderer().render(make_msg(blocks=[b]))
        assert "desktop msg" in r

    def test_render_key_value(self):
        b = KeyValueBlock(key="Status", value="Done")
        r = DesktopRenderer().render(make_msg(blocks=[b]))
        assert "Status" in r

    def test_render_list(self):
        b = ListBlock(title="L", items=[{"a": "1"}])
        r = DesktopRenderer().render(make_msg(blocks=[b]))
        assert "L" in r
