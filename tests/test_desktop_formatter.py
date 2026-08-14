# tests/test_desktop_formatter.py

from pilotstd.core.notification.desktop_formatter import (
    MAX_BODY_LENGTH,
    MAX_TITLE_LENGTH,
    format_for_desktop,
    render_for_desktop,
)


class TestEmojiReplacement:
    """Emoji 替换为纯文本"""

    def test_success_emoji(self):
        title, body = format_for_desktop("✅ 归档完成", "3个文件已处理")
        assert "[成功]" in title
        assert "✅" not in title

    def test_failure_emoji(self):
        title, body = format_for_desktop("❌ 扫描失败", "磁盘空间不足")
        assert "[失败]" in title
        assert "❌" not in title

    def test_timer_emoji(self):
        title, body = format_for_desktop("任务完成", "⏱️ 耗时 3.2s")
        assert "[耗时]" in body
        assert "⏱️" not in body

    def test_warning_emoji(self):
        title, body = format_for_desktop("⚠️ 注意", "内存占用较高")
        assert "[警告]" in title

    def test_info_emoji(self):
        title, body = format_for_desktop("ℹ️ 提示", "新版本可用")
        assert "[提示]" in title

    def test_multiple_emojis_in_one_message(self):
        title, body = format_for_desktop("✅ 归档完成", "✅ 5项成功 ❌ 2项失败 ⏱️ 耗时 1.5s")
        assert "✅" not in body
        assert "❌" not in body
        assert "⏱️" not in body
        assert "[成功]" in body
        assert "[失败]" in body
        assert "[耗时]" in body

    def test_no_emoji_passthrough(self):
        """无 Emoji 的消息原样保留"""
        title, body = format_for_desktop("普通标题", "普通内容")
        assert title == "普通标题"
        assert body == "普通内容"


class TestWhitespaceNormalization:
    """空白字符处理"""

    def test_newlines_to_spaces(self):
        title, body = format_for_desktop("标题", "第一行\n第二行\n第三行")
        assert "\n" not in body
        assert body == "第一行 第二行 第三行"

    def test_tabs_to_spaces(self):
        title, body = format_for_desktop("标题", "列A\t列B\t列C")
        assert "\t" not in body

    def test_multiple_spaces_collapsed(self):
        title, body = format_for_desktop("标题", "多余   空格   压缩")
        assert "  " not in body
        assert body == "多余 空格 压缩"

    def test_leading_trailing_whitespace_stripped(self):
        title, body = format_for_desktop("  标题  ", "  内容  ")
        assert title == "标题"
        assert body == "内容"

    def test_mixed_whitespace(self):
        title, body = format_for_desktop("标题", "行1\n\n  行2\t\t行3")
        assert body == "行1 行2 行3"


class TestTitleTruncation:
    """标题长度截断"""

    def test_short_title_unchanged(self):
        title, _ = format_for_desktop("短标题", "内容")
        assert title == "短标题"

    def test_exact_max_length_unchanged(self):
        text = "a" * MAX_TITLE_LENGTH
        title, _ = format_for_desktop(text, "内容")
        assert title == text
        assert not title.endswith("...")

    def test_over_max_length_truncated(self):
        text = "a" * (MAX_TITLE_LENGTH + 20)
        title, _ = format_for_desktop(text, "内容")
        assert len(title) == MAX_TITLE_LENGTH
        assert title.endswith("...")

    def test_truncation_preserves_prefix(self):
        title, _ = format_for_desktop("扫描任务：文件夹A/B/C/D/E/F/G/H/I/J/K/L/M/N 已成功完成归档处理", "内容")
        assert title.startswith("扫描任务")
        assert title.endswith("...")


class TestBodyTruncation:
    """正文长度截断"""

    def test_short_body_unchanged(self):
        _, body = format_for_desktop("标题", "短内容")
        assert body == "短内容"

    def test_exact_max_length_unchanged(self):
        text = "b" * MAX_BODY_LENGTH
        _, body = format_for_desktop("标题", text)
        assert body == text
        assert not body.endswith("...")

    def test_over_max_length_truncated(self):
        text = "b" * (MAX_BODY_LENGTH + 50)
        _, body = format_for_desktop("标题", text)
        assert len(body) == MAX_BODY_LENGTH
        assert body.endswith("...")


class TestEdgeCases:
    """边界情况"""

    def test_empty_title_and_body(self):
        title, body = format_for_desktop("", "")
        assert title == ""
        assert body == ""

    def test_only_emojis(self):
        title, body = format_for_desktop("✅❌", "⏱️⚠️ℹ️")
        assert "✅" not in title
        assert "❌" not in title
        assert title == "[成功][失败]"
        assert body == "[耗时][警告][提示]"

    def test_emoji_after_truncation_boundary(self):
        """Emoji 恰好出现在截断边界附近"""
        prefix = "x" * (MAX_BODY_LENGTH - 1)
        text = prefix + "✅"
        _, body = format_for_desktop("标题", text)
        assert len(body) == MAX_BODY_LENGTH
        assert "✅" not in body or body.endswith("...")

    def test_chinese_characters_count_correctly(self):
        """中文字符长度计算正确（不会被多字节编码干扰）"""
        text = "中" * MAX_TITLE_LENGTH
        title, _ = format_for_desktop(text, "内容")
        assert len(title) == MAX_TITLE_LENGTH

    def test_returns_tuple(self):
        result = format_for_desktop("标题", "内容")
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestRenderForDesktop:
    def test_renders_message_via_desktop_renderer(self):
        from pilotstd.core.notification.blocks import TextBlock
        from pilotstd.core.notification.channel import NotificationMessage
        msg = NotificationMessage(title="Test", body="fallback")
        msg.blocks = [TextBlock(text="hello world")]
        title, body = render_for_desktop(msg)
        assert isinstance(title, str)
        assert isinstance(body, str)
        assert "hello world" in body

    def test_renders_fallback_body(self):
        from pilotstd.core.notification.channel import NotificationMessage
        msg = NotificationMessage(title="Test", body="plain text")
        title, body = render_for_desktop(msg)
        assert "plain text" in body
