"""Telegram 渲染器（T-41/3 从 `renderer.py` 拆出，守 G-010）。

**职责**：MarkdownV2 转义、列表分隔、回调按钮载荷上限，以及 `TelegramRenderer` 本体。
**依赖**：共享基座 `renderer_base`（块渲染/分段）+ `renderer_links`（站内入口与按钮文案）。
"""

from __future__ import annotations

import re
from typing import Any

from pilotstd.i18n import t

from .blocks import KeyValueBlock, ListBlock, StatusChangeBlock, TextBlock
from .renderer_base import BlockRenderer, logger
from .renderer_links import action_label as _action_label
from .renderer_links import link_actions

_TELEGRAM_ESCAPE_CHARS = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")

_TELEGRAM_LIST_SEP = " \\| "

_TELEGRAM_CALLBACK_DATA_LIMIT = 64

class TelegramRenderer(BlockRenderer):
    """Telegram MarkdownV2 渲染器——先转义用户数据，再施加格式标记。"""

    def build_reply_markup(self, message: "Any") -> dict[str, Any] | None:
        """由 `message.actions` 生成 `inline_keyboard`；**无动作/无 token 时返回 `None`**。

        **设计决策（显式记录，勿"修"成每段都挂）**：按钮**只挂在最后一段**——分段是"消息太长"的
        物理切分，同一条通知被切成 N 段时，动作属于**这条通知**而非某一段；若每段都挂按钮，
        用户会看到 N 组重复按钮、且点任意一组效果相同（更糟的是 Telegram 会把每组都当成一次交互机会）。
        故调用方（`channels/telegram.py`）只对最后一段传 `reply_markup`。

        **`callback_data` 长度**：Telegram 限 **≤ 64 字节**（本仓 `notification_log.callback_data`
        的列注释亦写明该上限）。这里采用 `"<action>:<token>"`（`callback.py::_split_action` 的解析口径），
        token 形如 `<log_id>:<user_id>` ⇒ 实测长度约 10–20 字节，**远低于上限**；
        仍做防御：逐条校验字节长度，超限则**跳过该按钮并告警**（不发出必然被 Telegram 拒收的载荷）。

        **fail-safe**：`message.callback_data` 为空时**不下发回调按钮**（宁可不出按钮，也不发"点了没反应"的按钮）；
        但**链接型动作**（站内入口，见 `link_actions()`）**不依赖 token** ⇒ 即使没有 token 也应正常渲染。
        """
        from .callback import SUPPORTED_ACTIONS

        actions = list(getattr(message, "actions", []) or [])
        token = str(getattr(message, "callback_data", "") or "")
        row: list[dict[str, str]] = []
        # ① 链接型动作（站内入口）：TG 原生 URL 按钮，无需 token
        for spec in link_actions(message):
            args = getattr(spec, "args", None) or {}
            row.append({"text": _action_label(spec), "url": str(args.get("url") or "")})
        # ② 回调型动作（阶段 3）：需要签名 token；**无 token 一律跳过**（fail-safe）
        for spec in actions if token else []:
            action = str(getattr(spec, "action", "") or "")
            if action not in SUPPORTED_ACTIONS:
                continue
            if isinstance(getattr(spec, "args", None), dict) and spec.args.get("url"):
                continue  # 链接型动作已在 ① 渲染，避免重复
            data = f"{action}:{token}"
            if len(data.encode("utf-8")) > _TELEGRAM_CALLBACK_DATA_LIMIT:
                # 开发者日志用 ASCII（G-047 只允许用户可见文案走 i18n）
                logger.warning(
                    "telegram callback_data too long (%d bytes > %d); button skipped",
                    len(data.encode("utf-8")),
                    _TELEGRAM_CALLBACK_DATA_LIMIT,
                )
                continue
            label_key = str(getattr(spec, "label_key", "") or "")
            row.append({"text": t(label_key) if label_key else action, "callback_data": data})
        return {"inline_keyboard": [row]} if row else None

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
        lines: list[str] = [
            f"📋 *{self._escape(block.title)}*{t('notification.renderer.list_count').format(total=total)}"
        ]

        for item in block.items:
            parts: list[str] = []
            # 标准号/编号字段加粗展示，其余字段普通拼接
            for key, value in item.items():
                escaped_value = self._escape(value)
                if key == "number":
                    parts.append(f"*{escaped_value}*")
                else:
                    parts.append(escaped_value)
            # 分隔符本身也必须转义：`parts` 已各自转义，但分隔符是在**转义之后**拼入的，
            # 若直接用 `" | "`，`|` 会以未转义形态进入 MarkdownV2 → Telegram 返回
            # `HTTP 400: can't parse entities: Character '|' is reserved`。
            # 生产实测：`standard_first_registered` 因此**连续 7 次全部失败**（从未成功过）。
            lines.append(f"• {_TELEGRAM_LIST_SEP.join(parts)}")

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
