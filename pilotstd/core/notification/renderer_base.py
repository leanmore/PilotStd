"""渲染器共享基座（T-41/3 从 `renderer.py` 拆出，守 G-010）。

**为什么单独成模块**：`renderer.py` 同时承载“共享基座（块渲染/分段/尺寸/标签）”与四家渠道渲染器，
体积越过 G-010 的 400 有效行警戒线；基座是**被多渠道复用**的部分，拆出后既降体积、又让渠道渲染器
只依赖基座（单向依赖，无循环）。

**导入方向**：`renderer.py`（外观）与各渠道渲染器模块都从这里取基座；本模块不反向依赖它们。
"""

from __future__ import annotations

import logging

from pilotstd.i18n import t

from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    StatusChangeBlock,
    TextBlock,
)
from .channel import NotificationMessage

# 各渠道文本上限（T-41/3 从 `renderer.py` 迁入基座；主模块再导出以保持既有导入方兼容）
CHANNEL_TEXT_LIMITS: dict[str, tuple[int, str]] = {
    "telegram": (4096, "chars"),
    "wecom": (2048, "bytes"),
    "feishu": (4096, "chars"),
    "dingtalk": (4000, "chars"),
}

logger = logging.getLogger(__name__)

_LIST_FIELD_KEYS = {
    "number": "notification.renderer.field.number",
    "name": "notification.renderer.field.name",
    "status": "notification.renderer.field.status",
    "detail": "notification.renderer.field.detail",
    "path": "notification.renderer.field.path",
    "reason": "notification.renderer.field.reason",
    # 2026-10-05 通知聚合 B1：失败明细的 4 列（**必须登记**，否则渲染为「字段」占位——
    # `_field_label` 的兜底策略是绝不回退原始键名，见其 docstring）
    "standard_number": "notification.renderer.field.standard_number",
    "standard_name": "notification.renderer.field.standard_name",
    "error_type": "notification.renderer.field.error_type",
    "error_message": "notification.renderer.field.error_message",
    # 需求①的第四列＝"总数"（按 类型 × 标准号 × 标准名 归并后的条数）
    "count": "notification.renderer.field.count",
}

_SEGMENT_SUFFIX_KEY = "notification.segment.continued"

def _fallback_text() -> str:
    """渲染兜底占位文案（消息无结构块、无正文、无标题时用）。

    调用期取 t()：模块级常量会把语言固化在 import 时刻。
    """
    return t("notification.renderer.empty")

def _field_label(key: str) -> str:
    """把 ListBlock 条目的数据字段名翻译为可展示的表头/前缀文本。

    兜底：未登记或翻译缺失时返回通用占位「字段」（`_field_label_unknown`），
    **不回退为原始键名**——暴露 number/name 这类内部字段名正是本函数要消除的问题。
    """
    i18n_key = _LIST_FIELD_KEYS.get(key)
    if not i18n_key:
        return t("notification.renderer.field.unknown")
    resolved = t(i18n_key)
    # t() 缺键时 fail-loud 返回键本身；此处不能把键名当表头，故再兜一层
    if not resolved or resolved == i18n_key:
        return t("notification.renderer.field.unknown")
    return resolved

def _text_size(text: str, unit: str) -> int:
    """按渠道口径计算"文本长度"：字符数或 UTF-8 字节数（企微是字节口径）。"""
    return len(text.encode("utf-8")) if unit == "bytes" else len(text)

def split_for_channel(text: str, channel: str) -> list[str]:
    """把渲染后的文本按**渠道上限**切分为若干段（不丢信息；段间标「续 N/M」）。

    设计取舍（为什么这样切）：
    · **优先在换行处切**（参考 MoviePilot `telegram._split_plain_text` 的做法）：消息由"块/行"组成，
      在行间断开不会把一行拆成两半，用户看到的是完整条目；
      找不到换行（超长单行）才硬切，保证**每段都不超限**（宁可难看，不能超限被渠道拒收）。
    · **不做行数截断**（`MAX_FAILED_ROWS` 已作废）：条数由 payload 决定，长度由本函数负责。
    · 追加「续 N/M」只加在**第 2 段起**的末尾：不占用第 1 段的长度预算，且明确告知用户这是续段。
    · 若单段预算小于后缀本身（极端小上限），退化为"不加上限校验的硬切"会超限 ⇒ 此处直接返回原文本，
      由调用方按渠道错误处理（不静默丢弃信息）。
    """
    limit, unit = CHANNEL_TEXT_LIMITS.get(channel, (4096, "chars"))
    if _text_size(text, unit) <= limit:
        return [text]

    suffix_probe = _size_probe_suffix(limit, unit)
    budget = limit - _text_size(suffix_probe, unit)
    if budget <= 0:
        return [text]

    segments: list[str] = []
    remaining = text
    while remaining and _text_size(remaining, unit) > budget:
        cut = _find_cut(remaining, budget, unit)
        segments.append(remaining[:cut].rstrip("\n"))
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        segments.append(remaining)

    total = len(segments)
    if total > 1:
        # 「续 N/M」：第 2 段起标注，保证读者知道还有后续
        segments = [segments[0]] + [
            f"{seg}\n{suffix}" for seg, suffix in zip(segments[1:], _suffixes(total))
        ]
    return segments

def _size_probe_suffix(limit: int, unit: str) -> str:
    """预留后缀长度用的探针（取最长的「续 M/M」形态，避免最后一段超限）。"""
    probe = t(_SEGMENT_SUFFIX_KEY).format(n=99, total=99)
    del limit, unit  # 仅为签名对称，预留值由调用方按同一口径计算
    return probe

def _suffixes(total: int) -> list[str]:
    """生成第 2..M 段的后缀文案（i18n：notification.segment.continued）。"""
    return [t(_SEGMENT_SUFFIX_KEY).format(n=i, total=total) for i in range(2, total + 1)]

def _find_cut(text: str, budget: int, unit: str) -> int:
    """在 `budget` 内寻找切点：优先换行；否则硬切（返回字符下标）。"""
    if unit == "bytes":
        # 字节口径：逐字符累加，避免把多字节字符切坏
        used = 0
        best_newline = -1
        for idx, ch in enumerate(text):
            used += len(ch.encode("utf-8"))
            if used > budget:
                return best_newline if best_newline > 0 else max(idx, 1)
            if ch == "\n":
                best_newline = idx + 1
        return len(text)
    window = text[:budget]
    pos = window.rfind("\n")
    return pos + 1 if pos > 0 else max(budget, 1)

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
            text = message.title or _fallback_text()
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
        lines: list[str] = [
            f"{self._escape(block.title)}{t('notification.renderer.list_count').format(total=total)}"
        ]

        for item in block.items:
            parts: list[str] = []
            for key, value in item.items():
                # 字段名经 i18n 翻译（原实现直接暴露 number: 这类数据键）
                parts.append(f"{_field_label(key)}: {value}")
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
