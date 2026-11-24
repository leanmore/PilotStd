"""企业微信**模板卡片**渲染器（阶段 3 · Step 4 ①；从 `renderer.py` 拆出以守 G-010）。

**取证来源（[实现] 等级）**：第三方插件 `AWdress/MoviePilot-Plugins` 的
`plugins/awembypush/__init__.py:950-984` 有真实可用实现——应用消息端点
`cgi-bin/message/send?access_token=…`，报文形如：

```json
{"touser": "<user|@all>", "msgtype": "template_card", "agentid": "<id>",
 "template_card": {"card_type": "news_notice",
    "source": {"icon_url": …, "desc": …},
    "main_title": {"title": …, "desc": …},
    "card_image": {"url": …, "aspect_ratio": 2.25},
    "vertical_content_list": [{"title": …, "desc": …}],
    "jump_list": [{"type": 1, "url": …, "title": …}],
    "card_action": {"type": 1, "url": …}}}
```

**只产出已被实证的字段**：
· `card_type="news_notice"`（**不实现** `text_notice`：本次语料未见真实样例，不猜字段）；
· `card_image` **仅在有图时输出**（我方通知通常无图；该字段是否必填官方正文未取到 ⇒ 缺失时省略，
  由渠道层在平台拒收时**降级为文本**，见 `channels/wechat.py`）；
· `jump_list` / `card_action` 由**链接型动作**（站内入口）填充 ⇒ "查看详情"在企微里变成卡片跳转。

**与钉钉卡片的区别（重要）**：钉钉卡片按钮由**租户模板**定义（我方只能填 `cardParamMap`）；
企微 `template_card` 是**平台内置类型**，无需租户建模板 ⇒ 可直接产出完整卡片。
"""

from __future__ import annotations

import textwrap
from typing import Any

from pilotstd.i18n import t

from .blocks import KeyValueBlock, ListBlock, NotificationBlock, StatusChangeBlock, TextBlock
from .renderer import BlockRenderer
from .renderer_base import level_prefix
from .renderer_links import action_label, link_actions


class WeChatCardRenderer(BlockRenderer):
    """把通知消息渲染为企微 `template_card`（`msgtype=template_card` 的取值）。"""

    def render_card(self, message: Any) -> dict[str, Any]:
        blocks: list[NotificationBlock] = getattr(message, "blocks", [])
        items: list[dict[str, str]] = []
        for block in blocks:
            rendered = self._render_block(block)
            if isinstance(rendered, str) and rendered:
                # 块渲染结果按行拆进 `vertical_content_list`（企微卡片的"多行说明"结构）
                for line in rendered.splitlines():
                    if line.strip():
                        # 长名称拆成多行，避免 140 字截断后语义不完整
                        chunks = textwrap.wrap(line.strip(), width=140, break_long_words=True)
                        for chunk in chunks or [line.strip()[:140]]:
                            items.append({"title": "", "desc": chunk})
        if not items and (message.body or ""):
            items.append({"title": "", "desc": str(message.body)[:140]})

        # P0-3：`message.link`（如标准详情）此前在卡片里**完全不可见**。
        # 作为 `jump_list` 首项并让 `card_action` 指向它（卡片的主动作＝用户最想去的详情页）；
        # 既有站内入口动作（`view_detail`）保留为后续项，不互相顶掉。
        # 企微 `jump_list` 项的 `type` 是 **int**（1 = 跳转 URL），`url/title` 是 str，
        # 故值类型用 Any（此前注解写成 dict[str, str] 会让 mypy 判 int 不可赋）。
        jump_list: list[dict[str, Any]] = []
        detail_url = str(getattr(message, "link", "") or "").strip()
        if detail_url:
            jump_list.append({"type": 1, "url": detail_url, "title": t("notification.renderer.detail")})
        jump_list.extend(
            {
                "type": 1,  # 1 = 跳转 URL（与实证实现一致）
                "url": str((getattr(spec, "args", None) or {}).get("url") or ""),
                "title": action_label(spec),
            }
            for spec in link_actions(message)
        )

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
        if jump_list:
            card["jump_list"] = jump_list
            card["card_action"] = {"type": 1, "url": jump_list[0]["url"]}
        return card

    # ── 以下为 BlockRenderer 抽象方法的最小实现：本渲染器只走 `render_card()`，
    #    `render()`（str）用于渠道层的**降级文本**（卡片被平台拒收时改发文本消息）。
    def _render_text(self, block: TextBlock) -> str:
        return block.text

    def _render_key_value(self, block: KeyValueBlock) -> str:
        return f"{block.key}：{block.value}"

    def _render_status_change(self, block: StatusChangeBlock) -> str:
        return f"{block.label}: {block.old_value} → {block.new_value}"

    def _render_list(self, block: ListBlock) -> str:
        """列表块：标题 +「共 N 条」+ 逐行条目 + 完整列表链接（P1-1，此前三项全丢）。

        企微卡片正文是纯文本 `desc`（不解析 markdown），故完整列表链接写成「文案：URL」
        而不是 `[文案](URL)`，避免卡片里出现裸方括号语法。
        """
        total = block.total if block.total is not None else len(block.items)
        lines = [f"**{block.title}**{t('notification.renderer.list_count').format(total=total)}"]
        for item in block.items:
            lines.append("- " + " | ".join(str(v) for v in item.values()))
        if block.detail_url:
            lines.append(f"{t('notification.renderer.view_full_list')}：{block.detail_url}")
        return "\n".join(lines)
