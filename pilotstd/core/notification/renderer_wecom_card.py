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

from typing import Any

from .blocks import KeyValueBlock, ListBlock, NotificationBlock, StatusChangeBlock, TextBlock
from .renderer import BlockRenderer
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
                        items.append({"title": "", "desc": line.strip()[:140]})
        if not items and (message.body or ""):
            items.append({"title": "", "desc": str(message.body)[:140]})

        links = link_actions(message)
        jump_list = [
            {
                "type": 1,  # 1 = 跳转 URL（与实证实现一致）
                "url": str((getattr(spec, "args", None) or {}).get("url") or ""),
                "title": action_label(spec),
            }
            for spec in links
        ]

        card: dict[str, Any] = {
            "card_type": "news_notice",
            "source": {"desc": str(message.title or "")},
            "main_title": {"title": str(message.title or ""), "desc": ""},
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
        lines = [f"**{block.title}**"]
        for item in block.items:
            lines.append("- " + " | ".join(str(v) for v in item.values()))
        return "\n".join(lines)
