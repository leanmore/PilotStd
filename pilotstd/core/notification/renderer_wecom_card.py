"""企业微信**模板卡片**渲染器（阶段 3 · Step 4 ①；从 `renderer.py` 拆出以守 G-010）。

**官方字段契约（2026-11-25 批次 9 取证，此前留白项）**——`news_notice` 卡片的硬性要求：

· `card_image` 与 `image_text_area` **必填其一，不可都不填**；
· `card_action` **必填**，且 `type=1` 时**必须带 URL**；
· `vertical_content_list` **最多 4 条**，条目 `title` **必填**（建议 ≤26 字），
  `desc` 建议 ≤112 字（二级纯文本）；
· `jump_list` 最多 3 条。

取证来源：企业微信开发者中心《模板卡片类型》
（`https://developer.work.weixin.qq.com/document/path/101032`）与《结构体说明》
（`https://developer.work.weixin.qq.com/document/path/101839`）。

**卡型三选一结论：保留 `news_notice`**（不改 `text_notice`）：
· `text_notice` 同样要求 `card_action`，且**没有** `vertical_content_list` 结构——多行明细
  只能压进 `sub_title_text` / `horizontal_content_list`，信息量反而更差；
· 本仓 `news_notice` 已有可用实证语料（见下），改动面最小、风险最低。
无图时 `card_image` 用**站内静态透明占位图**（`{站点根}/notification-card.png`，
对应 `web/public/notification-card.png`）：不硬编码外部图片站、不引入坏图依赖。

**未配置 `web_base_url` 时**：没有合法 `card_action` URL 可填（`jump_list` 也空），
按项目"宁可不给链接，也不给坏链"的原则**不产出非法卡**；渠道层据此改发
**应用 markdown 消息**（`channels/wechat.py`，与 Webhook 共用 markdown 渲染器）——
因此「实际发出的卡」必定满足上述必填项（这也是 D1 的收口口径）。

**已实证字段**（第三方插件 `AWdress/MoviePilot-Plugins` 的 `awembypush`，报文结构）：

```json
{"touser": "<user|@all>", "msgtype": "template_card", "agentid": "<id>",
 "template_card": {"card_type": "news_notice",
    "source": {"desc": …},
    "main_title": {"title": …, "desc": …},
    "card_image": {"url": …},
    "vertical_content_list": [{"title": …, "desc": …}],
    "jump_list": [{"type": 1, "url": …, "title": …}],
    "card_action": {"type": 1, "url": …}}}
```
"""

from __future__ import annotations

import re
from typing import Any

from pilotstd.i18n import t

from .blocks import KeyValueBlock, ListBlock, NotificationBlock, StatusChangeBlock, TextBlock
from .renderer import BlockRenderer
from .renderer_base import level_prefix
from .renderer_links import action_label, link_actions

# 官方上限/建议值（取证见模块 docstring；均为**硬上限或官方建议**，超出会被 40058 拒收或观感差）
_CARD_ITEM_LIMIT = 4  # `vertical_content_list` 最多 4 条
_CARD_JUMP_LIMIT = 3  # `jump_list` 最多 3 条
_CARD_DESC_WIDTH = 112  # `desc` 建议 ≤112 字
_CARD_TITLE_WIDTH = 26  # 条目 `title` 建议 ≤26 字（不同版本文档写 26/38，取保守值）
_CARD_IMAGE_PATH = "/notification-card.png"  # 站内静态透明占位图（`web/public/`）

# 行内自然分隔符：优先按它们拆「标题 + 正文」（`title` 必填，不能靠空串占位）
_CARD_SEPARATORS = ("：", ": ", " | ")

# 句末标点（**不含英文 `.`**：详情 URL 里的点不能被当成句末，否则会把链接截断）
_SENTENCE_ENDS = "。；！？;!?"

# 站点根（`scheme://host[:port]`）：用正则而非 `urlsplit`，避免为非法地址引入 try/except
_ORIGIN_RE = re.compile(r"^(https?://[^/?#\s]+)", re.IGNORECASE)


def _plain_text(line: str) -> str:
    """把渲染行收敛成卡片可用的**纯文本**（D4：`desc` 不解析 markdown）。

    · 内联链接 `[文案](URL)` → `文案：URL`（保留可读信息，不显示裸方括号语法）；
    · 去掉加粗标记 `**` / `__`；
    · 去掉列表前缀 `- ` / `• ` / `* `（逐层剥，防嵌套前缀残留）。
    """
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1：\2", line or "")
    text = text.replace("**", "").replace("__", "").strip()
    changed = True
    while changed:
        changed = False
        for marker in ("- ", "• ", "* "):
            if text.startswith(marker):
                text = text[len(marker) :].strip()
                changed = True
    return text


def _split_long_line(text: str) -> list[str]:
    """把超宽行按句末标点切块（无标点则硬切），保证每块 ≤`_CARD_DESC_WIDTH` 字。

    为什么先切行（D5）：旧实现 body-only 路径 `str(body)[:140]` **硬截断丢尾部**；
    改为切块后逐块进 `vertical_content_list`，超出 4 条时由计数尾行明确提示。
    """
    if len(text) <= _CARD_DESC_WIDTH:
        return [text]
    chunks: list[str] = []
    rest = text
    while len(rest) > _CARD_DESC_WIDTH:
        window = rest[:_CARD_DESC_WIDTH]
        cut = max(window.rfind(ch) for ch in _SENTENCE_ENDS) + 1
        cut = cut if cut > 0 else _CARD_DESC_WIDTH
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest.strip())
    return [chunk for chunk in chunks if chunk]


def _split_title_desc(text: str) -> dict[str, str]:
    """把一行拆成 `title`（必填）与 `desc`（可选），**内容不丢**。

    优先在行内自然分隔符处拆（`标准号：GB/T 1-2020` ⇒ title=标准号、desc=GB/T 1-2020；
    `GB/T 1-2020 | 甲` ⇒ title=GB/T 1-2020、desc=甲）；无分隔符时短行整行当标题，
    长行按标题宽度切开（title + desc 拼回原文，绝不丢字）。
    """
    positions = [(text.find(sep), sep) for sep in _CARD_SEPARATORS if sep in text]
    if positions:
        idx, sep = min(positions)
        head = text[:idx].strip()
        tail = text[idx + len(sep) :].strip()
        if head and tail and len(head) <= _CARD_TITLE_WIDTH:
            return {"title": head, "desc": tail[:_CARD_DESC_WIDTH]}
    if len(text) <= _CARD_TITLE_WIDTH:
        return {"title": text, "desc": ""}
    return {"title": text[:_CARD_TITLE_WIDTH], "desc": text[_CARD_TITLE_WIDTH:].strip()[:_CARD_DESC_WIDTH]}


class WeChatCardRenderer(BlockRenderer):
    """把通知消息渲染为企微 `template_card`（`msgtype=template_card` 的取值）。"""

    def render_card(self, message: Any) -> dict[str, Any]:
        """渲染 `news_notice` 模板卡片（满足官方必填/上限契约，见模块 docstring）。

        仅当存在**合法跳转 URL** 时才输出 `jump_list` / `card_action`；`card_image` 与
        站内入口同源。无动作时返回的卡**不含**这些字段（渠道层判定后改发应用 markdown，
        不发送必然被平台拒收的卡）。
        """
        items = self._build_items(self._content_lines(message))
        jump_list = self._jump_list(message)
        # P0-2：级别前缀（warning/error）此前在卡片里**完全不可见**（27 个事件看不出严重度）。
        # 只在这里补一次（放 `main_title.desc`，紧贴主标题）；**不放进 `_render_block()`**——
        # 那会让降级文本路径（`render()` 基座也会加一次前缀）出现二次前缀。
        card: dict[str, Any] = {
            "card_type": "news_notice",
            "source": {"desc": str(message.title or "")},
            "main_title": {
                "title": str(message.title or ""),
                "desc": level_prefix(getattr(message, "level", "")),
            },
            "vertical_content_list": items,
        }
        image_url = self._card_image_url(message, jump_list)
        if image_url:
            card["card_image"] = {"url": image_url}
        if jump_list:
            card["jump_list"] = jump_list
            # `news_notice` 的 `card_action` 必填；主动作＝用户最想去的页面（详情链接优先）
            card["card_action"] = {"type": 1, "url": jump_list[0]["url"]}
        return card

    # ── 内容 → `vertical_content_list` ──

    def _content_lines(self, message: Any) -> list[str]:
        """收集卡片正文行：优先结构块渲染；无块时回退正文（D5：body-only 不再硬截断）。"""
        blocks: list[NotificationBlock] = getattr(message, "blocks", []) or []
        if blocks:
            lines: list[str] = []
            for block in blocks:
                rendered = self._render_block(block)
                if isinstance(rendered, str) and rendered:
                    lines.extend(rendered.splitlines())
            return lines
        body = str(getattr(message, "body", "") or "")
        return body.splitlines()

    def _build_items(self, lines: list[str]) -> list[dict[str, str]]:
        """把正文行映射为 `vertical_content_list`：条目 title 必填、≤4 条、超限带计数尾行。"""
        items: list[dict[str, str]] = []
        for line in lines:
            for piece in _split_long_line(_plain_text(line)):
                item = _split_title_desc(piece)
                if item["title"] or item["desc"]:
                    items.append(item)
        if len(items) > _CARD_ITEM_LIMIT:
            total = len(items)
            # 官方硬上限 4 条：保留前 3 条 + 计数尾行（明确告知被压缩，不静默丢）
            items = items[: _CARD_ITEM_LIMIT - 1]
            items.append({"title": t("notification.wecom.card.more").format(total=total), "desc": ""})
        return items

    def _jump_list(self, message: Any) -> list[dict[str, Any]]:
        """跳转项（≤3 条）：`message.link` 在首位（详情页），其后是站内入口动作。"""
        jump_list: list[dict[str, Any]] = []
        detail_url = str(getattr(message, "link", "") or "").strip()
        if detail_url:
            jump_list.append(
                {"type": 1, "url": detail_url, "title": t("notification.renderer.detail")}
            )
        jump_list.extend(
            {
                "type": 1,  # 1 = 跳转 URL（与实证实现一致）
                "url": str((getattr(spec, "args", None) or {}).get("url") or ""),
                "title": action_label(spec),
            }
            for spec in link_actions(message)
        )
        return jump_list[:_CARD_JUMP_LIMIT]

    def _card_image_url(self, message: Any, jump_list: list[dict[str, Any]]) -> str:
        """占位图 URL：与站内入口**同源**的静态透明图（见模块 docstring 的取舍）。

        无站内入口/详情链接 ⇒ 推导不出站点根 ⇒ 返回空串（渠道层改发 markdown）。
        """
        for spec in link_actions(message):
            if getattr(spec, "action", "") == "view_detail":
                match = _ORIGIN_RE.match(str((getattr(spec, "args", None) or {}).get("url") or ""))
                if match:
                    return f"{match.group(1)}{_CARD_IMAGE_PATH}"
        detail = str(getattr(message, "link", "") or "").strip()
        first_jump = str(jump_list[0].get("url") or "") if jump_list else ""
        match = _ORIGIN_RE.match(detail) or _ORIGIN_RE.match(first_jump)
        return f"{match.group(1)}{_CARD_IMAGE_PATH}" if match else ""

    # ── 以下为 BlockRenderer 抽象方法的最小实现：本渲染器只走 `render_card()`，
    #    `render()`（str）用于渠道层的**文本降级**兜底（卡片/ markdown 都被拒时）。
    def _render_text(self, block: TextBlock) -> str:
        return block.text

    def _render_key_value(self, block: KeyValueBlock) -> str:
        return f"{block.key}：{block.value}"

    def _render_status_change(self, block: StatusChangeBlock) -> str:
        return f"{block.label}: {block.old_value} → {block.new_value}"

    def _render_list(self, block: ListBlock) -> str:
        """列表块：纯文本标题 +「共 N 条」+ `•` 条目 + 完整列表链接（D4）。

        与 Markdown 渲染器的区别：**不输出** `**加粗**` 与 `- 列表前缀`——企微卡片
        `desc` 是纯文本，旧实现让用户看到字面 `**`/`- `；完整列表链接写成
        「文案：URL」而不是 `[文案](URL)`，避免卡片里出现裸方括号语法。
        """
        total = block.total if block.total is not None else len(block.items)
        lines = [f"{block.title}{t('notification.renderer.list_count').format(total=total)}"]
        for item in block.items:
            lines.append("• " + " | ".join(str(v) for v in item.values()))
        if block.detail_url:
            lines.append(f"{t('notification.renderer.view_full_list')}：{block.detail_url}")
        return "\n".join(lines)
