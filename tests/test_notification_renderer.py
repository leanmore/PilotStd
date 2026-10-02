"""core/notification/renderer.py 补测 — BlockRenderer + 4 个子类全覆盖。"""

from pilotstd.core.notification.blocks import (
    KeyValueBlock,
    ListBlock,
    StatusChangeBlock,
    TextBlock,
)
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import (
    BlockRenderer,
    DesktopRenderer,
    FeishuCardRenderer,
    MarkdownRenderer,
    TelegramRenderer,
)
from pilotstd.core.status import Status
from pilotstd.i18n import set_language


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
        # 渲染器最终防线：空结果回退标题，标题空则用固定占位文案（杜绝空文本发送）
        r = BlockRenderer().render(make_msg(title="", body="", blocks=[]))
        assert r == "(通知内容为空)"

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

    def test_render_unknown_block_type(self):
        """未知 Block 类型回退 str()。"""
        from pilotstd.core.notification.blocks import NotificationBlock
        b = NotificationBlock()
        r = BlockRenderer().render(make_msg(blocks=[b]))
        assert "NotificationBlock" in r

    def test_render_title_empty(self):
        r = BlockRenderer().render(make_msg(title="", body="body", blocks=[]))
        assert r == "body"


class TestListFieldLabelI18n:
    """第 6 批：ListBlock 字段名必须经 i18n 翻译，不得直接暴露数据键名。

    回归背景：飞书卡片表头原实现取 `block.items[0].keys()` 原样当列头，
    中文用户看到 `number` / `name`；基类纯文本渲染同理会渲染出 `number: GB/T 1-2024`。
    """

    def test_base_renderer_uses_translated_field_name(self):
        b = ListBlock(title="L", items=[{"number": "GB/T 1-2024"}])
        set_language("zh_CN")
        rendered = BlockRenderer().render(make_msg(blocks=[b]))
        assert "标准号" in rendered
        assert "number" not in rendered

    def test_feishu_header_uses_translated_field_name(self):
        b = ListBlock(title="L", items=[{"number": "GB/T 1-2024", "name": "标准一"}])
        set_language("zh_CN")
        card = FeishuCardRenderer().render(make_msg(blocks=[b]))
        table = next(e for e in card["elements"] if e.get("tag") == "table")
        headers = [c["text"].strip("*") for c in table["header"]]
        assert headers == ["标准号", "名称"]

    def test_header_follows_language_switch(self):
        """调用期取 t()：切换语言后表头必须跟着变（模块级求值会固化语言）。"""
        b = ListBlock(title="L", items=[{"number": "GB/T 1-2024"}])
        set_language("en")
        en_headers = [
            c["text"].strip("*")
            for e in FeishuCardRenderer().render(make_msg(blocks=[b]))["elements"]
            if e.get("tag") == "table"
            for c in e["header"]
        ]
        set_language("zh_TW")
        tw_headers = [
            c["text"].strip("*")
            for e in FeishuCardRenderer().render(make_msg(blocks=[b]))["elements"]
            if e.get("tag") == "table"
            for c in e["header"]
        ]
        assert en_headers == ["Standard No."]
        assert tw_headers == ["標準號"]

    def test_unknown_field_falls_back_to_placeholder_not_raw_key(self):
        """未登记字段名回退为通用占位，绝不回退成原始键名。"""
        b = ListBlock(title="L", items=[{"internal_code_xyz": "v"}])
        set_language("zh_CN")
        card = FeishuCardRenderer().render(make_msg(blocks=[b]))
        table = next(e for e in card["elements"] if e.get("tag") == "table")
        headers = [c["text"].strip("*") for c in table["header"]]
        assert headers == ["字段"]
        assert "internal_code_xyz" not in str(card)

    def test_field_values_are_never_translated(self):
        """只翻译字段名，行数据必须原样保留。"""
        b = ListBlock(title="L", items=[{"number": "GB/T 1-2024", "name": "标准一"}])
        set_language("zh_CN")
        card = FeishuCardRenderer().render(make_msg(blocks=[b]))
        table = next(e for e in card["elements"] if e.get("tag") == "table")
        assert table["rows"] == [[{"tag": "text", "text": "GB/T 1-2024"}, {"tag": "text", "text": "标准一"}]]


class TestTelegramRenderer:
    def test_render_title_bold_with_block(self):
        b = TextBlock(text="msg")
        r = TelegramRenderer().render(make_msg(title="Alert", blocks=[b]))
        assert "*Alert*" in r

    def test_render_title_empty(self):
        r = TelegramRenderer()._render_title("")
        assert r == ""

    def test_escape_special_chars(self):
        r = TelegramRenderer()
        assert r._escape("a_b") == r"a\_b"

    def test_escape_empty(self):
        r = TelegramRenderer()
        assert r._escape("") == ""

    def test_render_key_value(self):
        b = KeyValueBlock(key="K", value="V")
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        assert "K: V" in r

    def test_render_status_change(self):
        b = StatusChangeBlock(label="L", old_value="A", new_value="B")
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        assert "L:" in r

    def test_render_list_number_bold(self):
        b = ListBlock(title="R", items=[{"number": "GB/T 1", "status": Status.ACTIVE.value}])
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        assert "*GB/T 1*" in r

    def test_render_list_separator_is_escaped(self):
        """★ 列表**字段分隔符**必须转义为 `\\|`。

        缺陷背景（生产实测）：`_render_list` 原先写 `' | '.join(parts)` ——
        `parts` 已各自转义，但**分隔符是在转义之后拼入的**，故 `|` 以未转义形态
        进入 MarkdownV2，Telegram 返回：
        `HTTP 400: can't parse entities: Character '|' is reserved and must be escaped`。
        受影响事件 `standard_first_registered` **连续 7 次全部失败**（从未成功过）。

        判别力：把分隔符改回 `" | "` → 本用例 FAIL。
        """
        b = ListBlock(title="R", items=[{"number": "GB/T 1", "name": "N"}])
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        assert r"\|" in r, f"分隔符未转义：{r!r}"
        # 每个条目行里不得出现**未转义**的 ` | `
        for line in r.splitlines():
            if line.startswith("•"):
                assert " | " not in line, f"条目行含未转义分隔符：{line!r}"

    def test_render_list_separator_escape_not_doubled(self):
        """★ 值本身含 `|` 时，值与分隔符**各转义一次**（不得二次转义）。"""
        b = ListBlock(title="R", items=[{"number": "A|B", "name": "N"}])
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        # 值里的 | 转义一次 → 渲染中出现 `A\|B`（源码字面量 r"A\|B"）
        assert r"A\|B" in r, f"值内的 | 应转义一次：{r!r}"
        # 不得出现二次转义（即 `A\\|B`，源码字面量 "A\\\\|B"）
        assert "A\\\\|B" not in r, f"出现了二次转义：{r!r}"

    def test_render_list_multi_field_all_escaped(self):
        """多字段条目的每个值都转义（保留原行为）。"""
        b = ListBlock(title="R", items=[{"number": "GB/T 1.1-2020", "name": "含.点"}])
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        assert "GB/T 1\\.1\\-2020" in r
        assert "含\\.点" in r

    def test_render_list_with_detail_url(self):
        b = ListBlock(title="L", items=[{"k": "v"}], detail_url="https://t.me")
        r = TelegramRenderer().render(make_msg(blocks=[b]))
        assert "https://t" in r  # Telegram 渲染器转义特殊字符（. → \.）

    def test_bold(self):
        assert TelegramRenderer()._bold("x") == "*x*"

    def test_mono(self):
        assert TelegramRenderer()._mono("x") == "`x`"


class TestMarkdownRenderer:
    def test_render_title_heading(self):
        b = TextBlock(text="content")
        r = MarkdownRenderer().render(make_msg(title="H", blocks=[b]))
        assert "## H" in r

    def test_render_title_empty(self):
        r = MarkdownRenderer()._render_title("")
        assert r == ""

    def test_render_key_value(self):
        b = KeyValueBlock(key="K", value="V")
        r = MarkdownRenderer().render(make_msg(blocks=[b]))
        assert "**K**" in r

    def test_render_status_change(self):
        b = StatusChangeBlock(label="L", old_value="A", new_value="B")
        r = MarkdownRenderer().render(make_msg(blocks=[b]))
        assert "**L**" in r

    def test_render_list_with_url(self):
        b = ListBlock(title="L", items=[{"k": "v"}], detail_url="http://x.com")
        r = MarkdownRenderer().render(make_msg(blocks=[b]))
        assert "http://x.com" in r

    def test_render_list_number_bold(self):
        b = ListBlock(title="L", items=[{"number": "GB/T 1", "name": "std"}])
        r = MarkdownRenderer().render(make_msg(blocks=[b]))
        assert "**GB/T 1**" in r


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

    def test_render_empty_list(self):
        b = ListBlock(title="Empty", items=[])
        r = FeishuCardRenderer().render(make_msg(blocks=[b]))
        assert "无数据" in str(r["elements"])

    def test_render_fallback_body(self):
        r = FeishuCardRenderer().render(make_msg(title="T", body="fallback"))
        assert r["elements"][0]["content"] == "fallback"

    def test_render_title_returns_empty(self):
        """飞书标题在 header 中处理，_render_title 返回空。"""
        assert FeishuCardRenderer()._render_title("Any") == ""


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

    def test_render_status_change(self):
        b = StatusChangeBlock(label="State", old_value="A", new_value="B")
        r = DesktopRenderer().render(make_msg(blocks=[b]))
        assert "State" in r

    def test_render_empty_list(self):
        b = ListBlock(title="NoItems", items=[])
        r = DesktopRenderer().render(make_msg(blocks=[b]))
        assert "NoItems" in r

    def test_desktop_preview_never_exposes_raw_field_name(self):
        """桌面预览不得暴露原始数据键名（第 6/7 批字段名 i18n 的回归防护）。

        实测当前实现只取首条首**值**做预览（`{title}：{first} 等 {total} 条`），
        字段名根本不出现——比 FeishuCardRenderer 更保守。本测试锁定该性质：
        若未来有人把预览改成拼接字段名，必须走 `_field_label()` 而非原始键。
        """
        b = ListBlock(title="扫描结果", items=[{"number": "GB/T 1-2024"}], total=3)
        set_language("zh_CN")
        r = DesktopRenderer().render(make_msg(blocks=[b]))
        assert "number" not in r
        assert "GB/T 1-2024" in r
        assert "扫描结果" in r

    def test_render_list_uses_first_value_only(self):
        """预览只取首条首值，不展开多字段（桌面气泡空间受限）。"""
        b = ListBlock(title="L", items=[{"number": "GB/T 1", "name": "标准一"}], total=1)
        set_language("zh_CN")
        r = DesktopRenderer().render(make_msg(blocks=[b]))
        assert "GB/T 1" in r
        assert "标准一" not in r
