# 模块：项目/核心//锁脚本
"""通知消息的**动作**与**附件**规格（阶段 1c）。

## 为什么单独成模块（而不是塞进 `channel.py`）

1. **`channel.py` 是"消息容器"**（`NotificationMessage` 一个 dataclass + 13+12 个字段），
   且它已有一个历史职责：对旧基类名 `NotificationChannel` 做废弃转发（`__getattr__`）。
   再往里放两个独立数据类型，会让"容器"与"元素规格"两个概念混在一处；
2. **反向依赖风险**：规格迟早要被渲染层/阶段 3 的回调层消费。放在 `channel.py` 会让
   消费方为了拿 `ActionSpec` 而 import 整个消息容器（含其 `blocks` 依赖链）；
   独立模块只有 `dataclasses` 一个依赖，无环；
3. **词表就近**：`ACTIONS` 闭集与 `ACTION_STYLES` 是"动作"这一概念的词表，
   放在定义 `ActionSpec` 的文件里，改词表时只需看一个文件（与 `blocks.py` 的
   "一种概念一个模块"一致）。

## 两个不可变约定

- 两者都 `@dataclass(frozen=True)`（可哈希、可进 set、可作 dict 键）；
- `args` 虽是 dict 字段（frozen 只保证"不重新赋值字段"，不保证内容不可变）——
  **契约：调用方不得修改已构造的 `args`**；需要变更时新建实例。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

__all__ = [
    "ACTIONS",
    "ACTION_STYLES",
    "ATTACHMENT_KINDS",
    "ActionSpec",
    "AttachmentSpec",
    "specs_to_jsonable",
]

# ── 动作白名单（**闭集**，禁止自由扩展）────────────────────────────────────────
# 新增动作的准入条件：它必须能被 §2.2 的权限模型表达（最低权限 + 是否改变状态），
# 且解码侧（阶段 3 的回调 handler）有对应的处置分支。理由见 02-目标架构.md §2.2。
ACTIONS: tuple[str, ...] = (
    "view_detail",  # 打开站内详情/日志（不改变状态；全渠道，可降级为链接）
    "open_logs",  # 打开通知日志页（不改变状态；同上）
    "retry",  # 重试失败项（**改变状态**，写 task_queue；仅交互渠道 + 管理员）
    "ignore",  # 忽略/确认（仅回执，记 ack_status=acted）
    "snooze",  # 稍后提醒（**延迟**，写延后队列）
    "mark_done",  # 人工标记完成（**改变状态**；仅交互渠道 + 管理员）
)

# 样式仅用于渠道渲染器映射（primary/danger 需渠道支持；不支持时按 default 渲染）
ACTION_STYLES: tuple[str, ...] = ("default", "primary", "danger")

# 附件种类（闭集）。阶段 1c 只登记种类，不实现发送（四渠道当前均无图片发送代码）。
ATTACHMENT_KINDS: tuple[str, ...] = ("image", "file")


@dataclass(frozen=True)
class ActionSpec:
    """一条可交互动作的声明（按钮的唯一数据源）。

    字段语义与权限模型见 docs/plans/notification-redesign/02-目标架构.md §2.2。

    **`__hash__` 为什么手写**：`frozen=True` 只会阻止"重新赋值字段"，dataclass 自动生成的
    `__hash__` 仍会把**全部**字段纳入哈希——而 `args` 是 dict（不可哈希），
    于是 `hash(ActionSpec(...))` 会抛 `TypeError`。故显式定义 `__hash__`：
    **只取不可变字段**（等于"按动作身份哈希"），而 `__eq__` 仍由 dataclass 生成、
    **包含 args**（两条 `retry` 若参数不同应视为不同动作）。两者语义分工明确：
    相等性看完整内容，哈希看身份。
    """

    action: str  # 必须取自 ACTIONS（闭集）；构造期不校验，由契约测试锁定
    label_key: str  # i18n 键，**调用期取 t()**（沿用既有约定，禁止模块级求值）
    style: str = "default"  # 取自 ACTION_STYLES
    args: dict[str, Any] = field(default_factory=dict)  # 动作参数（如 record_id）
    requires_confirm: bool = False  # 破坏性动作须二次确认（retry / mark_done）

    def __hash__(self) -> int:
        """按**动作身份**哈希（不含可变的 args）。"""
        return hash((self.action, self.label_key, self.style, self.requires_confirm))
@dataclass(frozen=True)
class AttachmentSpec:
    """一条附件的声明（阶段 1c 只承载数据，不实现渠道发送）。"""

    kind: str  # 取自 ATTACHMENT_KINDS
    url: str
    name: str = ""
    size: int = 0


def specs_to_jsonable(specs: list[Any]) -> list[dict[str, Any]]:
    """把规格列表转成可 JSON 序列化的字典列表（供落库/入队）。

    行为：
    - `ActionSpec` / `AttachmentSpec` → `dataclasses.asdict`
    - **已经是 dict 的项原样保留** —— 这条很重要：读取端（`_json_codec.loads_list`）
      故意**不**重建 dataclass 实例，而是给纯字典列表，保证往返幂等
      （`dumps(specs_to_jsonable(dumps 后再读的结果))` 不变形）；
    - 其它类型 → 跳过（防御：不因一个畸形元素丢掉整条通知）。
    """
    out: list[dict[str, Any]] = []
    for item in specs or []:
        if isinstance(item, (ActionSpec, AttachmentSpec)):
            out.append(asdict(item))
        elif isinstance(item, dict):
            out.append(item)
    return out
