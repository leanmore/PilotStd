"""D2 回归：TG「详情」链接行必须按 MarkdownV2 合法转义（否则整条 400 丢消息）。

证据背景（`docs/plans/2026-11-25-p1-notify-refresh.md` §4-D2）：
`BlockRenderer.render()` 在**逐块转义完成之后**追加 `detail_link_line()`，但 Telegram 没有覆盖
该追加段——裸 URL 里的 `.`/`-`/`_` 等 18 个 MarkdownV2 保留字符未加反斜杠 ⇒ 设置
`parse_mode=MarkdownV2` 后 Telegram 返回 `HTTP 400: can't parse entities`，
7 个带 link 事件**整条丢失**（`standard_status_changed` / `standard_first_registered` /
`validity_standard_failed` / `download_failed` / `favorite_created` / `download_started` /
`download_complete`）。

修法：基座提供可覆盖的追加段钩子；Telegram 用官方**内联链接语法** `[文案](URL)`
（官方规则：链接目标部分只需转义 `)` 与 `\\`，其余字符在目标里合法）。

本文件的判别力来自一个**独立实现的极简 MarkdownV2 校验器**：它按 Telegram 官方规则
解析输出（正文区的 18 个保留字符必须已转义、链接目标只接受 `\\)` / `\\\\`），
而不是只断言"输出里出现了某个字符串"——后者对转义回归无判别力。
"""

from __future__ import annotations

from pilotstd.core.notification.blocks import TextBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import MarkdownRenderer
from pilotstd.core.notification.renderer_telegram import TelegramRenderer
from pilotstd.i18n import t

# Telegram Bot API《MarkdownV2 style》规定的 18 个保留字符
_RESERVED = set("_*[]()~`>#+-=|{}.!")


def _find_unescaped(text: str, char: str, start: int) -> int:
    """返回 `char` 第一次**未转义**出现的下标；找不到返回 -1。"""
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == char:
            return i
        i += 1
    return -1


def _assert_plain_markdownv2(text: str) -> None:
    """校验一段**纯正文**：除反斜杠转义对外的保留字符都会让 Telegram 400。"""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            assert i + 1 < len(text), f"结尾悬空反斜杠，MarkdownV2 非法: {text!r}"
            i += 2
            continue
        assert ch not in _RESERVED, f"未转义保留字符 {ch!r}（下标 {i}）: {text!r}"
        i += 1


def assert_markdownv2_valid(text: str) -> None:
    """极简 MarkdownV2 校验器（与实现无关的独立口径）。

    解析 `[标签](目标)` 内联链接：标签内部按正文规则校验，目标部分只接受
    `\\)` / `\\\\` 两种转义（裸 `)` 会提前截断目标）。链接之外的正文按正文规则校验。
    任何一处不合法都会像 Telegram 一样"解析失败"。
    """
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":
            end = _find_unescaped(text, "]", i + 1)
            assert end != -1, f"链接标签未闭合: {text!r}"
            _assert_plain_markdownv2(text[i + 1 : end])
            assert text[end + 1 : end + 2] == "(", f"链接标签后缺少 `(`: {text!r}"
            close = _find_unescaped(text, ")", end + 2)
            assert close != -1, f"链接目标未闭合（裸 `)` 会把 URL 截断）: {text!r}"
            dest = text[end + 2 : close]
            assert "\n" not in dest, f"链接目标出现换行: {text!r}"
            j = 0
            while j < len(dest):
                if dest[j] == "\\":
                    assert j + 1 < len(dest), f"链接目标结尾悬空反斜杠: {text!r}"
                    assert dest[j + 1] in "()\\", (
                        f"链接目标只允许 `\\)` / `\\\\` 转义，实测 {dest[j:j + 2]!r}: {text!r}"
                    )
                    j += 2
                    continue
                assert dest[j] != ")", f"链接目标含未转义 `)`: {text!r}"
                j += 1
            i = close + 1
            continue
        assert ch not in _RESERVED, f"未转义保留字符 {ch!r}（下标 {i}）: {text!r}"
        i += 1


def _msg(link: str | None) -> NotificationMessage:
    """最小消息（标题留空，使校验器只需处理正文与链接两种文法）。"""
    return NotificationMessage(
        title="",
        body="正文",
        blocks=[TextBlock(text="正文")],
        link=link,
    )


def test_tg_detail_link_with_dot_and_dash_passes_markdownv2() -> None:
    """含 `.` / `-` 的 detail_link 渲染后必须能通过 MarkdownV2 校验（D2 主判据）。"""
    link = "https://std.example.com/standards/GB/T 12345-2020"
    text = TelegramRenderer().render(_msg(link))
    assert_markdownv2_valid(text), text
    # 链接目标保持原样（官方规则：目标部分只有 `)`/`\\` 需要转义；`.`/`-` 无需）
    assert f"[{t('notification.renderer.detail')}]({link})" in text
    # 修复前的裸 URL 形态（`详情：https://…`）会触发 400，必须消失
    assert f"{t('notification.renderer.detail')}：https://" not in text


def test_tg_detail_link_with_underscore_and_percent_passes_markdownv2() -> None:
    """`_` / `%` / 查询串里的保留字符同样不得破坏解析。"""
    link = "https://std.example.com/standards/GB_T-1-2020?q=a_b&x=1.5"
    text = TelegramRenderer().render(_msg(link))
    assert_markdownv2_valid(text)
    assert f"[{t('notification.renderer.detail')}]({link})" in text


def test_tg_detail_link_escapes_parenthesis_and_backslash_in_target() -> None:
    """官方规则：链接目标内的 `)` 与 `\\` 必须转义，否则目标会被提前截断。"""
    link = "https://std.example.com/a)b\\c"
    text = TelegramRenderer().render(_msg(link))
    assert_markdownv2_valid(text)
    assert "https://std.example.com/a\\)b\\\\c" in text


def test_tg_detail_link_absent_when_message_has_no_link() -> None:
    """无链接 ⇒ 不追加详情行（既有行为不变）。"""
    text = TelegramRenderer().render(_msg(None))
    assert t("notification.renderer.detail") not in text


def test_tg_level_prefix_still_rendered_exactly_once() -> None:
    """追加段钩子不得把级别前缀吃掉或翻倍（同一基座路径）。"""
    msg = _msg("https://std.example.com/x.y")
    msg.level = "warning"
    text = TelegramRenderer().render(msg)
    from pilotstd.core.notification.renderer_base import level_prefix

    assert text.count(level_prefix("warning")) == 1
    assert_markdownv2_valid(text)


def test_markdown_channel_detail_line_stays_plain() -> None:
    """其它渠道（企微/钉钉 Webhook 走 `MarkdownRenderer`）不因 TG 修复被改动。"""
    link = "https://std.example.com/standards/GB/T 1-2020"
    text = MarkdownRenderer().render(_msg(link))
    assert f"{t('notification.renderer.detail')}：{link}" in text
    assert "](" not in text  # 不得把详情行变成链接语法（会改变既有渠道呈现）
