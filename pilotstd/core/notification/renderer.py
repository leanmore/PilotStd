# 模块：项目/核心//渲染器脚本
"""Block 渲染器——模板方法模式，将 Block 列表渲染为渠道专属格式。

基类定义骨架 render() → _render_title() + _render_block() 逐块分发。
子类实现 _render_text/_render_key_value/_render_status_change/_render_list。
_escape() 由子类覆盖做渠道特殊字符转义。
"""

from __future__ import annotations

import re

from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    StatusChangeBlock,
    TextBlock,
)
from .channel import NotificationMessage

# 渲染最终兜底文案：消息无结构块、无正文、无标题时的占位（杜绝空文本发送）
_FALLBACK_TEXT = "(通知内容为空)"


class BlockRenderer:
    """Block 渲染器基类——将结构化 Block 列表渲染为纯文本。

    子类实现: _render_text, _render_key_value, _render_status_change, _render_list。
    可选覆盖: _escape 渠道转义, _render_title 标题, _block_separator 块分隔符。
    """

    # ──公开接口──

    def render(self, message: NotificationMessage) -> str:
        """将通知消息渲染为渠道文本。

        消息若带结构块则逐块渲染；
        若仅有正文则回退为纯文本输出。

        最终兜底：任何路径下渲染结果都不为空字符串——
        空结果回退标题，标题也空则使用固定占位文案。
        """
        blocks: list[NotificationBlock] = getattr(message, "blocks", [])
        if not blocks:
            # 回退：降级为纯文本
            text = message.body if message.body else ""
        else:
            parts: list[str] = []
            title_part = self._render_title(message.title)
            if title_part:
                parts.append(title_part)

            for block in blocks:
                rendered = self._render_block(block)
                if rendered:
                    parts.append(rendered)

            text = self._block_separator().join(parts)

        # 最终防线：永不返回空字符串（聚合消息 blocks 丢失等历史缺陷的兜底）
        text = text.strip()
        if not text:
            text = message.title or _FALLBACK_TEXT
        return text

    # ── 渲染调度 ──

    def _render_block(self, block: NotificationBlock) -> str:
        """按类型分发渲染。"""
        if isinstance(block, TextBlock):
            return self._render_text(block)
        if isinstance(block, KeyValueBlock):
            return self._render_key_value(block)
        if isinstance(block, StatusChangeBlock):
            return self._render_status_change(block)
        if isinstance(block, ListBlock):
            return self._render_list(block)
        return str(block)

    # ── 子类需实现的方法 ──

    def _render_text(self, block: TextBlock) -> str:
        """渲染纯文本块。"""
        return self._escape(block.text)

    def _render_key_value(self, block: KeyValueBlock) -> str:
        """渲染键值对块，默认格式 'key: value'。"""
        return f"{self._escape(block.key)}: {self._escape(block.value)}"

    def _render_status_change(self, block: StatusChangeBlock) -> str:
        """渲染状态变更块，默认格式 'label: old → new'。"""
        return f"{self._escape(block.label)}: {self._escape(block.old_value)} → {self._escape(block.new_value)}"

    def _render_list(self, block: ListBlock) -> str:
        """渲染列表块——标题 + 逐行条目的默认格式。"""
        total = block.total if block.total is not None else len(block.items)
        lines: list[str] = [f"{self._escape(block.title)}（共 {total} 条）"]

        for item in block.items:
            parts: list[str] = []
            for key, value in item.items():
                parts.append(f"{key}: {value}")
            lines.append("  - " + " | ".join(self._escape(p) for p in parts))

        if block.detail_url:
            lines.append(self._escape(block.detail_url))

        return "\n".join(lines)

    # ── 可选覆盖的方法 ──

    def _render_title(self, title: str) -> str:
        """渲染消息标题。"""
        return self._escape(title) if title else ""

    def _block_separator(self) -> str:
        """Block 之间的分隔符。"""
        return "\n\n"

    def _escape(self, text: str) -> str:
        """转义渠道特殊字符。基类默认不做转义，子类按需覆盖。"""
        return text


# ═══════════════════════════════════════════════════════════════════════════ 分隔
# 电报渲染器（2）
# ═══════════════════════════════════════════════════════════════════════════ 分隔

# 电报2中必须反斜杠转义的字符
_TELEGRAM_ESCAPE_CHARS = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")


class TelegramRenderer(BlockRenderer):
    """Telegram MarkdownV2 渲染器——先转义用户数据，再施加格式标记。"""

    # ── 标题 ──

    def _render_title(self, title: str) -> str:
        if not title:
            return ""
        return f"*{self._escape(title)}*"

    # ──锁渲染──

    def _render_text(self, block: TextBlock) -> str:
        return self._escape(block.text)

    def _render_key_value(self, block: KeyValueBlock) -> str:
        return f"{self._escape(block.key)}: {self._escape(block.value)}"

    def _render_status_change(self, block: StatusChangeBlock) -> str:
        return f"{self._escape(block.label)}: {self._escape(block.old_value)} → {self._escape(block.new_value)}"

    def _render_list(self, block: ListBlock) -> str:
        """Telegram 列表：📋 标题 + • 条目，number 加粗。"""
        total = block.total if block.total is not None else len(block.items)
        lines: list[str] = [f"📋 *{self._escape(block.title)}*（共 {total} 条）"]

        for item in block.items:
            parts: list[str] = []
            # 标准号/编号字段加粗展示，其余字段普通拼接
            for key, value in item.items():
                escaped_value = self._escape(value)
                if key == "number":
                    parts.append(f"*{escaped_value}*")
                else:
                    parts.append(escaped_value)
            lines.append(f"• {' | '.join(parts)}")

        if block.detail_url:
            lines.append(self._escape(block.detail_url))

        return "\n".join(lines)

    # ──2转义──

    def _escape(self, text: str) -> str:
        """对 Telegram MarkdownV2 的 18 个特殊字符做反斜杠转义。

        转义范围：_ * [ ] ( ) ~ ` > # + - = | { } . !
        注意：此方法只转义用户数据，不应在已加好格式标记的字符串上调用。
        """
        if not text:
            return ""
        return _TELEGRAM_ESCAPE_CHARS.sub(r"\\\1", text)

    def _block_separator(self) -> str:
        """Telegram 消息块间用单空行分隔。"""
        return "\n\n"

    def _bold(self, text: str) -> str:
        return f"*{text}*"

    def _mono(self, text: str) -> str:
        return f"`{text}`"


# ═══════════════════════════════════════════════════════════════════════════ 分隔
# 渲染器（钉钉/企业微信）
# ═══════════════════════════════════════════════════════════════════════════ 分隔


class MarkdownRenderer(BlockRenderer):
    """通用 Markdown 渲染器——钉钉/企业微信 markdown。不转义特殊字符。"""

    # ── 标题 ──

    def _render_title(self, title: str) -> str:
        if not title:
            return ""
        return f"## {title}"

    # ──锁渲染──

    def _render_text(self, block: TextBlock) -> str:
        return block.text

    def _render_key_value(self, block: KeyValueBlock) -> str:
        return f"**{block.key}**：{block.value}"

    def _render_status_change(self, block: StatusChangeBlock) -> str:
        return f"**{block.label}**\n\n{block.old_value} → {block.new_value}"

    def _render_list(self, block: ListBlock) -> str:
        """Markdown 列表：加粗标题 + - 条目 + 可选链接。"""
        total = block.total if block.total is not None else len(block.items)
        lines: list[str] = [f"**{block.title}**（共 {total} 条）"]

        for item in block.items:
            parts: list[str] = []
            for key, value in item.items():
                if key == "number":
                    parts.append(f"**{value}**")
                else:
                    parts.append(value)
            lines.append(f"- {' | '.join(parts)}")

        if block.detail_url:
            lines.append(f"\n[查看完整列表]({block.detail_url})")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════ 分隔
# 飞书卡片渲染器
# ═══════════════════════════════════════════════════════════════════════════ 分隔

# 飞书→卡片颜色映射
_FEISHU_COLOR_MAP = {
    "error": "red",
    "warning": "orange",
    "info": "blue",
}


class FeishuCardRenderer(BlockRenderer):
    """飞书交互式卡片渲染器。render() 返回 dict（卡片 JSON），非字符串。"""

    def render(self, message: NotificationMessage) -> dict:  # type: ignore[override]
        """将通知消息渲染为飞书交互式卡片 dict。"""
        blocks: list[NotificationBlock] = getattr(message, "blocks", [])
        color = _FEISHU_COLOR_MAP.get(message.level, "grey")

        elements: list[dict] = []
        if not blocks:
            # 回退：降级为元素
            elements.append({"tag": "markdown", "content": message.body or ""})
        else:
            for block in blocks:
                rendered = self._render_block(block)
                # 飞书的__锁对锁可能返回多元素列表
                if isinstance(rendered, list):
                    elements.extend(rendered)
                elif rendered:
                    elements.append(rendered)

        return {
            "header": {
                "title": {"tag": "plain_text", "content": message.title or ""},
                "template": color,
            },
            "elements": elements,
        }

    def _render_block(self, block: NotificationBlock):
        if isinstance(block, ListBlock):
            return self._render_list(block)
        return super()._render_block(block)

    # ──锁渲染──

    def _render_text(self, block: TextBlock) -> dict:  # type: ignore[override]
        return {"tag": "markdown", "content": block.text}

    def _render_key_value(self, block: KeyValueBlock) -> dict:  # type: ignore[override]
        return {"tag": "markdown", "content": f"**{block.key}**：{block.value}"}

    def _render_status_change(self, block: StatusChangeBlock) -> dict:  # type: ignore[override]
        return {
            "tag": "markdown",
            "content": f"**{block.label}**\n{block.old_value} → {block.new_value}",
        }

    def _render_list(self, block: ListBlock) -> list[dict]:  # type: ignore[override]
        """飞书列表：标题 markdown + table + 可选按钮。"""
        elements: list[dict] = []

        if not block.items:
            elements.append({"tag": "markdown", "content": f"**{block.title}**：无数据"})
        else:
            total = block.total if block.total is not None else len(block.items)
            elements.append({"tag": "markdown", "content": f"**{block.title}**（共 {total} 条）"})

            # 从第一条的生成表头
            header_keys = list(block.items[0].keys())
            header_cells = [{"tag": "text", "text": f"**{k}**"} for k in header_keys]
            rows = []
            for item in block.items:
                row = [{"tag": "text", "text": item.get(k, "")} for k in header_keys]
                rows.append(row)

            table = {
                "tag": "table",
                "header": header_cells,
                "rows": rows,
            }
            elements.append(table)

        if block.detail_url:
            elements.append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看完整列表"},
                            "type": "primary",
                            "url": block.detail_url,
                        }
                    ],
                }
            )

        return elements

    def _render_title(self, title: str) -> str:
        return ""  # 飞书标题在 render() 的 header 中处理


# ═══════════════════════════════════════════════════════════════════════════ 分隔
# 桌面渲染器（）
# ═══════════════════════════════════════════════════════════════════════════ 分隔


class DesktopRenderer(BlockRenderer):
    """桌面 Toast 渲染器——极致精简，仅做摘要预览。

    ListBlock 不展开，只取首条第一字段做预览（Windows Toast body 上限 120 字符）。
    """

    def _render_text(self, block: TextBlock) -> str:
        return block.text

    def _render_key_value(self, block: KeyValueBlock) -> str:
        return f"{block.key}：{block.value}"

    def _render_status_change(self, block: StatusChangeBlock) -> str:
        return f"{block.label}：{block.old_value} → {block.new_value}"

    def _render_list(self, block: ListBlock) -> str:
        """桌面列表：仅取首条首字段预览，不展开全量条目。"""
        total = block.total if block.total is not None else len(block.items)
        if not block.items:
            return block.title
        # 只取第一条的第一个字段值做预览
        first_item = block.items[0]
        first_value = list(first_item.values())[0] if first_item else ""
        return f"{block.title}：{first_value} 等 {total} 条"

    def _block_separator(self) -> str:
        """桌面气泡空间有限，单空格分隔。"""
        return " "
