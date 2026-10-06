"""渲染器的**共享链接助手**（阶段 3 · Step 1/Step 4 ①；从 `renderer.py` 拆出以守 G-010）。

为什么单独成模块：`link_actions()` / `action_label()` 被**四渠道**渲染器（TG / 飞书 / 钉钉 / 企微）
以及 Markdown 渲染器共用；把它们留在 `renderer.py` 会让该文件越过 500 有效行的门禁上限。
本模块**只依赖** i18n 与动作规格，不依赖任何渲染器 ⇒ 不产生循环导入。

约定：`ActionSpec.args["url"]` 存在即为"链接型动作"（站内入口）——它**不带 `callback_data`**、
不参与回调，各渠道按自身能力渲染（TG/飞书＝按钮；企微/钉钉 webhook＝Markdown 链接；
钉钉互动卡片＝写进 `cardParamMap.content`；企微模板卡片＝`jump_list`）。
"""

from __future__ import annotations

from typing import Any

from pilotstd.i18n import t


def link_actions(message: Any) -> list[Any]:
    """取消息里**带 URL 的动作**（站内入口按钮/链接的唯一来源）。"""
    out: list[Any] = []
    for spec in list(getattr(message, "actions", []) or []):
        args = getattr(spec, "args", None) or {}
        url = str(args.get("url") or "").strip() if isinstance(args, dict) else ""
        if url:
            out.append(spec)
    return out


def action_label(spec: Any) -> str:
    """动作展示文案（`label_key` 经 i18n；缺键回退动作名，绝不显示空按钮）。"""
    key = str(getattr(spec, "label_key", "") or "")
    if key:
        label = t(key)
        if label and label != key:
            return label
    return str(getattr(spec, "action", "") or "")


def link_markdown(message: Any) -> str:
    """把链接型动作渲染成 Markdown 链接串（企微/钉钉 webhook 用；无动作返回空串）。"""
    parts = [
        f"[{action_label(spec)}]({str((getattr(spec, 'args', None) or {}).get('url') or '')})"
        for spec in link_actions(message)
    ]
    return " | ".join(parts)
