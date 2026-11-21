"""交互能力的渠道无关底座（阶段 B，基础先行）。

设计依据：[02-framework-update.md](../../../docs/plans/notification-system-design/02-framework-update.md) §2.3
"**基础先行**：先做渠道无关的公共能力（**改写句柄抽象**、回调端点骨架、验签骨架），再按渠道启用"。

本模块只放**数据契约**，不放渠道实现：
- `ChannelCapabilities`：渠道自述"能否回调 / 能否编辑 / 编辑锚点是什么"；
- `MessageHandle`：渠道无关的**改写句柄** —— 四家的锚点并不统一
  （[01-channel-capabilities.md](../../../docs/plans/notification-system-design/01-channel-capabilities.md) §四 结论 3：
  飞书/TG 用 `message_id`、钉钉用 `outTrackId`、企微未找到），故不能假设统一 `message_id`。
"""

from dataclasses import dataclass

# 编辑锚点取值（闭集）：新增锚点必须同时补渠道实现与测试
ANCHOR_MESSAGE_ID = "message_id"
ANCHOR_OUT_TRACK_ID = "out_track_id"


@dataclass(frozen=True)
class ChannelCapabilities:
    """渠道交互能力自述。

    `note_key` 为能力缺失时的**说明键**（i18n），供日志/界面解释"为什么不能"，
    避免用户把"渠道限制"误判为"系统故障"。
    """

    supports_callback: bool = False
    supports_edit: bool = False
    edit_anchor: str = ""
    note_key: str = ""
    # 内容能力（2026-11-21 补，D-2 模块化缺口）：上层按能力判断，不按渠道名写死
    supports_image: bool = False
    supports_mention: bool = False
    supports_buttons: bool = False


@dataclass(frozen=True)
class MessageHandle:
    """渠道无关的改写句柄：`(channel, anchor, value)`。

    例：Telegram 编辑用 `MessageHandle("telegram", ANCHOR_MESSAGE_ID, "12345")`；
    钉钉卡片更新（待补证）将用 `ANCHOR_OUT_TRACK_ID`。
    """

    channel: str
    anchor: str
    value: str

# 渠道内容能力矩阵（**单一来源**）：新增渠道时在此登记，上层不写 if/elif
_CHANNEL_CAPABILITIES: dict[str, ChannelCapabilities] = {
    "wechat": ChannelCapabilities(
        supports_callback=True,
        supports_edit=False,
        note_key="notification.capability.note.wechat",
        supports_mention=True,
    ),
    "feishu": ChannelCapabilities(
        supports_callback=True,
        supports_edit=True,
        edit_anchor=ANCHOR_MESSAGE_ID,
        note_key="notification.capability.note.feishu",
        supports_buttons=True,
    ),
    "telegram": ChannelCapabilities(
        supports_callback=True,
        supports_edit=True,
        edit_anchor=ANCHOR_MESSAGE_ID,
        note_key="notification.capability.note.telegram",
        supports_buttons=True,
    ),
    "dingtalk": ChannelCapabilities(
        supports_callback=False,
        supports_edit=False,
        edit_anchor=ANCHOR_OUT_TRACK_ID,
        note_key="notification.capability.note.dingtalk",
    ),
}


def channel_capabilities(channel: str) -> ChannelCapabilities:
    """按渠道取能力声明；未知渠道返回“全不支持”（不抛异常，便于上层降级）。"""
    return _CHANNEL_CAPABILITIES.get((channel or "").strip(), ChannelCapabilities())
