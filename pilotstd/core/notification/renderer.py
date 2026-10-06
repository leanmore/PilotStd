# 模块：项目/核心//渲染器脚本
"""Block 渲染器——模板方法模式，将 Block 列表渲染为渠道专属格式。

基类定义骨架 render() → _render_title() + _render_block() 逐块分发。
子类实现 _render_text/_render_key_value/_render_status_change/_render_list。
_escape() 由子类覆盖做渠道特殊字符转义。
"""

from __future__ import annotations

from pilotstd.i18n import t

from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    StatusChangeBlock,
    TextBlock,
)
from .channel import NotificationMessage
from .renderer_base import CHANNEL_TEXT_LIMITS
from .renderer_links import action_label as _action_label
from .renderer_links import link_actions

# ── 共享基座与 Telegram 渲染器（实现在 `renderer_base.py` / `renderer_telegram.py`；
#    T-41/3 拆分，此处**再导出**保持公开面）──
__all__ = [
    "CHANNEL_TEXT_LIMITS",
    "DesktopRenderer",
    "DingTalkCardRenderer",
    "FeishuCardRenderer",
    "MarkdownRenderer",
    "BlockRenderer",
    "TelegramRenderer",
    "_LIST_FIELD_KEYS",
    "_SEGMENT_SUFFIX_KEY",
    "_TELEGRAM_CALLBACK_DATA_LIMIT",
    "_TELEGRAM_ESCAPE_CHARS",
    "_TELEGRAM_LIST_SEP",
    "_fallback_text",
    "_field_label",
    "_find_cut",
    "_size_probe_suffix",
    "_suffixes",
    "_text_size",
    "logger",
    "split_for_channel",
]

from .renderer_base import (  # noqa: E402
    _LIST_FIELD_KEYS,
    _SEGMENT_SUFFIX_KEY,
    BlockRenderer,
    _fallback_text,
    _field_label,
    _find_cut,
    _size_probe_suffix,
    _suffixes,
    _text_size,
    logger,
    split_for_channel,
)
from .renderer_telegram import (  # noqa: E402
    _TELEGRAM_CALLBACK_DATA_LIMIT,
    _TELEGRAM_ESCAPE_CHARS,
    _TELEGRAM_LIST_SEP,
    TelegramRenderer,
)

# `link_actions()` / `action_label()` 已迁至 `renderer_links.py`（四渠道渲染器共用；
# 留在本文件会越过 G-010 的 500 有效行上限）。此处经顶部 import 复用其实现。


# ListBlock.items 的字段名 → i18n 键（渲染期取 t()：字段名是**数据键**，
# 直接当展示文本会让中文用户看到 number / name 这类英文键名）。
# 未登记的字段走 _field_label 的兜底，绝不回退成原始键名。




# 各渠道「单条消息」上限（上限值, 计数口径）；来源与口径逐条写在注释里——
# **不写成字符串**：G-047（Python 侧 i18n 硬编码检查）只拦"新增中文字面量"，说明性文字放注释即可。
#   · telegram 4096 字符 —— Telegram Bot API 官方：sendMessage.text 0-4096 字符（转义后仍是同一字符串）；
#   · wecom 2048 字节 —— 企业微信应用消息文本的官方口径是**字节**，故本仓按 UTF-8 字节数计；
#   · feishu 4096 字符 —— **未验证**：飞书按 UTF-16 单元计数、官方数字本轮未取到 ⇒ 取保守值；
#   · dingtalk 4000 字符 —— **未验证**：仅有社区口径，官方 API 条款本轮未取到 ⇒ 取保守值。

# 分段后追加的「续 N/M」标记模板（第 2 段起）；i18n 键见 notification.segment.continued

# Telegram `callback_data` 上限：**64 字节**（官方限制；本仓 notification_log.callback_data 列注释同口径）














# ═══════════════════════════════════════════════════════════════════════════ 分隔
# 电报渲染器（2）
# ═══════════════════════════════════════════════════════════════════════════ 分隔

# 电报2中必须反斜杠转义的字符

# 列表条目的字段分隔符（**已转义**形态）。
# 不能把它拼在"已转义的值"之后再行转义——那会连值一起二次转义；
# 故这里预先给出转义后的字面量，供 `_render_list` 直接 join。




# ═══════════════════════════════════════════════════════════════════════════ 分隔
# 渲染器（钉钉/企业微信）
# ═══════════════════════════════════════════════════════════════════════════ 分隔


class MarkdownRenderer(BlockRenderer):
    """通用 Markdown 渲染器——钉钉/企业微信 markdown。不转义特殊字符。"""

    def render(self, message: NotificationMessage) -> str:
        """正文 + **站内入口 Markdown 链接**。

        为什么是链接而不是按钮：**企微 webhook 与钉钉 webhook 只支持 markdown**（无法带按钮），
        故按用户裁定"企微 Webhook 渲染为 Markdown 链接"；同一个渲染器也服务钉钉 webhook 形态。
        """
        text = super().render(message)
        links = link_actions(message)
        if links:
            rendered = " | ".join(
                f"[{_action_label(spec)}]({str((getattr(spec, 'args', None) or {}).get('url') or '')})"
                for spec in links
            )
            text = f"{text}\n\n{rendered}" if text else rendered
        return text

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
        lines: list[str] = [
            f"**{block.title}**{t('notification.renderer.list_count').format(total=total)}"
        ]

        for item in block.items:
            parts: list[str] = []
            for key, value in item.items():
                if key == "number":
                    parts.append(f"**{value}**")
                else:
                    parts.append(value)
            lines.append(f"- {' | '.join(parts)}")

        if block.detail_url:
            lines.append(f"\n[{t('notification.renderer.view_full_list')}]({block.detail_url})")

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

        # 阶段 3 · Step 1：链接型动作（站内入口）渲染为卡片的 **URL 按钮**——
        # 此前 `render()` **完全不消费 `message.actions`**，故飞书卡片上的按钮从未出现过。
        links = link_actions(message)
        if links:
            buttons = [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": _action_label(spec)},
                    "type": "default",
                    "url": str((getattr(spec, "args", None) or {}).get("url") or ""),
                }
                for spec in links
            ]
            elements.append({"tag": "action", "actions": buttons})

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
            elements.append(
                {
                    "tag": "markdown",
                    "content": f"**{block.title}**{t('notification.renderer.list_empty')}",
                }
            )
        else:
            total = block.total if block.total is not None else len(block.items)
            elements.append(
                {
                    "tag": "markdown",
                    "content": f"**{block.title}**{t('notification.renderer.list_count').format(total=total)}",
                }
            )

            # 表头：字段名经 i18n 翻译后再展示（原实现直接暴露 number/name 等数据键）
            header_keys = list(block.items[0].keys())
            header_cells = [{"tag": "text", "text": f"**{_field_label(k)}**"} for k in header_keys]
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
                            "text": {
                                "tag": "plain_text",
                                "content": t("notification.renderer.view_full_list"),
                            },
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


class DingTalkCardRenderer(BlockRenderer):
    """钉钉互动卡片渲染器（阶段 S）。

    **为什么不用 `render()` 覆盖**：基类 `render()` 声明返回 `str`，返回 dict 的覆盖需要
    `# type: ignore[override]`（既有 `FeishuCardRenderer` 如此）。本项目禁止类型忽略指令，
    故本渲染器单独提供 `render_card()`，由渠道层显式调用。

    **模板参数契约**：钉钉卡片模板由**租户自行创建**，其变量名由模板定义；本渲染器统一产出
    三个参数名（`title` / `content` / `level`），租户建模板时按此命名即可。
    """

    def render_card(self, message: NotificationMessage) -> dict:
        """把通知消息渲染为钉钉卡片实例的 `cardData`（`cardParamMap` 形态）。"""
        blocks: list[NotificationBlock] = getattr(message, "blocks", [])
        parts: list[str] = []
        for block in blocks:
            rendered = self._render_block(block)
            if isinstance(rendered, str) and rendered:
                parts.append(rendered)
        content = "\n\n".join(parts) if parts else (message.body or "")
        # 阶段 3 · Step 1：卡片按钮由**租户模板**定义（我方模板契约只有 title/content/level）
        # ⇒ 站内入口以 **Markdown 链接**写进 content（无需租户改模板即可用）。
        links = link_actions(message)
        if links:
            rendered = " | ".join(
                f"[{_action_label(spec)}]({str((getattr(spec, 'args', None) or {}).get('url') or '')})"
                for spec in links
            )
            content = f"{content}\n\n{rendered}" if content else rendered
        return {
            "cardParamMap": {
                "title": message.title or "",
                "content": content,
                "level": message.level or "info",
            }
        }


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
        return t("notification.renderer.desktop_preview").format(
            title=block.title, first=first_value, total=total
        )

    def _block_separator(self) -> str:
        """桌面气泡空间有限，单空格分隔。"""
        return " "
