"""企微 `template_card` 官方字段契约回归（D1/D4/D5/D6 批次 9）。

证据背景（`docs/plans/2026-11-25-p1-notify-refresh.md` §4-D1）：
`news_notice` 卡片有**硬性契约**，当前渲染器多处不满足，企微（错误码 40058）会拒收整张卡，
导致卡片修复在生产上不可达。官方取证（企业微信开发者中心）：

- 《模板卡片类型》`https://developer.work.weixin.qq.com/document/path/101032`：
  `card_image` 与 `image_text_area` **必填其一**；`card_action` 在 `news_notice` 中**必填**；
- 《结构体说明》`https://developer.work.weixin.qq.com/document/path/101839`：
  `vertical_content_list` **最多 4 条**；条目的 `title` **必填**（建议 ≤26 字）、
  `desc` 建议 ≤112 字；`jump_list` 最多 3 条；`card_image.url` 必填。

三选一取舍（本次结论，写进 `renderer_wecom_card.py` 注释与交付报告）：
**保留 `news_notice`**（不改 `text_notice`）——`text_notice` 同样要求 `card_action`，
且会丢掉 `vertical_content_list` 的多行明细结构；本仓已有 `news_notice` 的实证语料，
风险最低。无图时的 `card_image` 用**站内静态透明占位图**（与站内入口同源，
`{web_base_url}/notification-card.png`），不引入外部硬编码图片地址。
未配置 `web_base_url` 时**不产出非法卡**（无合法 `card_action` URL 可填，且项目原则是
"宁可不给链接，也不给坏链"）⇒ 渠道层改发**应用 markdown 消息**（D3），卡片仅在有合法
动作时发送——因此"已发送的卡"必定满足官方必填项。
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from pilotstd.core.notification._links import attach_web_actions
from pilotstd.core.notification.blocks import ListBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer_wecom_card import WeChatCardRenderer
from pilotstd.i18n import t

BASE = "https://std.example.com"


class _Cfg:
    def __init__(self, value: str | None = BASE) -> None:
        self._v: dict[str, Any] = {} if value is None else {"notification.web_base_url": value}

    def get(self, key: str, default: Any = None) -> Any:
        return self._v.get(key, default)


def _msg(title: str = "扫描完成", body: str = "共 10 条，全部成功") -> NotificationMessage:
    msg = NotificationMessage(title=title)
    msg.body = body
    return msg


def _linked(msg: NotificationMessage) -> NotificationMessage:
    """模拟分发层：`_dispatcher.send_now` 会给每条消息挂站内入口动作。"""
    attach_web_actions(msg, _Cfg())
    return msg


def _card_items(card: dict[str, Any]) -> list[dict[str, str]]:
    return list(card.get("vertical_content_list") or [])


# ── D1：官方必填项 ──────────────────────────────────────────────────────────


def test_card_satisfies_news_notice_required_contract() -> None:
    """有站内入口时，卡片必须满足 `news_notice` 全部**硬性**必填项。"""
    card = WeChatCardRenderer().render_card(_linked(_msg()))
    assert card["card_type"] == "news_notice"
    # ① card_image 必填其一（我们用透明占位图，与站内入口同源）
    assert card["card_image"]["url"].startswith(BASE), card
    # ② card_action 必填，且 type=1 时必须带 URL
    assert card["card_action"]["type"] == 1
    assert card["card_action"]["url"]
    # ③ jump_list ≤3
    assert len(card["jump_list"]) <= 3
    # ④ vertical_content_list ≤4 且每条 title 必填
    items = _card_items(card)
    assert 1 <= len(items) <= 4
    assert all(item["title"] for item in items), f"条目 title 不得为空: {items}"


def test_card_image_placeholder_is_site_static_asset() -> None:
    """占位图必须来自站内静态资源（不硬编码外部图片站，避免坏图/隐私）。"""
    card = WeChatCardRenderer().render_card(_linked(_msg()))
    assert card["card_image"]["url"] == f"{BASE}/notification-card.png"


def test_card_vertical_item_title_uses_line_label() -> None:
    """条目 `title` 取行内自然标签（字段名/首个列表值），`desc` 放内容。"""
    msg = _msg(body="标准号：GB/T 12345-2020")
    card = WeChatCardRenderer().render_card(_linked(msg))
    assert _card_items(card) == [{"title": "标准号", "desc": "GB/T 12345-2020"}]


def test_card_list_truncated_to_four_with_count_tail() -> None:
    """列表行超 4 时**截断到 ≤4 并计数**：尾部条目给「共 N 条」提示。"""
    msg = _msg(body="")
    msg.blocks = [
        ListBlock(
            title="失败明细",
            items=[{"standard_number": f"GB/T {i}-2020"} for i in range(8)],
            total=8,
        )
    ]
    card = WeChatCardRenderer().render_card(_linked(msg))
    items = _card_items(card)
    assert len(items) <= 4, f"官方上限 4 条，实测 {len(items)}: {items}"
    dumped = json.dumps(card, ensure_ascii=False)
    # 计数提示：形如「共 N 条」；N = 被压缩前的段数（标题 1 + 8 行 = 9）
    assert "9" in dumped and t("notification.wecom.card.more").format(total=9) in dumped


def test_card_list_at_limit_still_renders_all_items() -> None:
    """未超限（列表 2 行 + 标题 = 3 段）时不得截断。"""
    msg = _msg(body="")
    msg.blocks = [
        ListBlock(
            title="新登记",
            items=[{"standard_number": "GB/T 1-2020"}, {"standard_number": "GB/T 2-2021"}],
            total=2,
        )
    ]
    card = WeChatCardRenderer().render_card(_linked(msg))
    items = _card_items(card)
    joined = " ".join(i["title"] + i["desc"] for i in items)
    assert "GB/T 1-2020" in joined and "GB/T 2-2021" in joined
    assert len(items) <= 4


def test_card_without_link_does_not_fabricate_required_fields() -> None:
    """未配置 `web_base_url` ⇒ 无合法动作可填，**不产出非法卡**（渠道层改发 markdown）。"""
    card = WeChatCardRenderer().render_card(_msg())
    assert "card_action" not in card
    assert "jump_list" not in card
    assert "card_image" not in card


# ── D4：卡片 desc 是纯文本，不得出现 markdown 字面量 ─────────────────────────


def test_card_desc_has_no_literal_markdown() -> None:
    """`vertical_content_list[].desc` 是纯文本：不得出现 `**` / `- ` / 裸 `[x](url)`。"""
    msg = _msg(body="")
    msg.blocks = [
        ListBlock(
            title="失败明细",
            items=[{"standard_number": "GB/T 1-2020", "error_type": "not_found"}],
            total=1,
            detail_url="https://std.example.com/standards/list",
        )
    ]
    card = WeChatCardRenderer().render_card(_linked(msg))
    for item in _card_items(card):
        for field in ("title", "desc"):
            text = item[field]
            assert "**" not in text, f"卡片 {field} 含字面 markdown 加粗: {text!r}"
            assert not text.startswith("- "), f"卡片 {field} 含字面列表前缀: {text!r}"
            assert "](" not in text, f"卡片 {field} 含裸 markdown 链接语法: {text!r}"


# ── D5/D6：body-only 不再 140 字符硬截断，desc 宽度 ≤112 ─────────────────────


def test_body_only_not_hard_truncated_and_desc_width_capped() -> None:
    """300 字 body-only：内容按整行/整句切分（不丢字），单条 `desc` ≤112。"""
    body = "测" * 300
    card = WeChatCardRenderer().render_card(_linked(_msg(body=body)))
    items = _card_items(card)
    # 全部内容可还原（标题 + 正文拼接 = 原文；3 段 ≈112×3 未触发截断）
    restored = "".join(item["title"] + item["desc"] for item in items)
    assert restored == body, f"body-only 内容丢失或被硬截断: {len(restored)} != {len(body)}"
    assert all(len(item["desc"]) <= 112 for item in items), items


def test_body_only_multiline_keeps_lines_as_separate_items() -> None:
    """多行 body-only 按行成条，而不是压成一行/硬截断。"""
    card = WeChatCardRenderer().render_card(_linked(_msg(body="第一行\n第二行\n第三行")))
    titles = [item["title"] for item in _card_items(card)]
    assert titles[:3] == ["第一行", "第二行", "第三行"]


def test_long_sentence_desc_is_cut_at_sentence_boundary() -> None:
    """超长单句：在句末标点处切块（而不是 140 字处生硬截断）。"""
    sentence = "这是一句完整的话。"
    body = sentence * 40
    card = WeChatCardRenderer().render_card(_linked(_msg(body=body)))
    items = _card_items(card)
    joined = "".join(item["title"] + item["desc"] for item in items)
    # 4 段以内不触发截断 ⇒ 内容逐字可还原（判"按句切块、不丢字"）
    assert joined == body, f"超长正文未按句切块（内容丢失）: {len(joined)} != {len(body)}"
    # 每块 `desc` 都在宽度上限内
    assert all(len(item["desc"]) <= 112 for item in items)


def test_card_renderer_still_produces_degradation_text() -> None:
    """`render()`（str）仍可用于文本降级路径（行为不变）。"""
    msg = _msg()
    text = WeChatCardRenderer().render(msg)
    assert "共 10 条" in text


@pytest.mark.parametrize("level", ["warning", "error"])
def test_card_level_prefix_in_main_title_once(level: str) -> None:
    """D-2 的级别前缀仍在 `main_title.desc` 且恰好一次（本次契约改动不得回归）。"""
    from pilotstd.core.notification.renderer_base import level_prefix

    msg = _msg()
    msg.level = level
    dumped = json.dumps(WeChatCardRenderer().render_card(_linked(msg)), ensure_ascii=False)
    assert dumped.count(level_prefix(level)) == 1
