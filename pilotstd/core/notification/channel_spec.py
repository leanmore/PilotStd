# 模块：项目/核心//渠道规格脚本
"""渠道规格（SSOT）——四个通知渠道的唯一声明源。

设计约束（见 docs/plans/notification-system-design/07-impl-design-A.md §一）：
1. 本模块是**纯数据叶子**：**不 import 渠道实现类**。若在此 import `channels/*`，
   则 `channel.py`（R1 需读本模块的 `CHANNEL_NAMES`）→ 本模块 → `channels/*`
   → `channels.base` → `channel.py` 会形成**部分初始化导入环**。故实现位置以
   `module` / `cls_name` 字符串登记，由 manager 在运行期解析。
2. **声明一律静态字面量**（门禁 G-045 以 `ast.parse` 读取本文件，不做运行期推导）；
   仅 `CHANNEL_NAMES` 是派生视图（非第二份声明）。
3. 两个标签键分属两个命名空间，各有唯一消费者：
   - `label_key`：**前端** locales 键（`web/src/locales/*.json`），UI 渲染用；
   - `legacy_label_key`：**后端** i18n 键（`pilotstd/i18n/*.json`），
     `get_config_schema()` 的兼容形状用；
   - `label`：字面量兜底（决策者裁决 N6：4 处标签保持英文，如 `Bot Token`）。
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CHANNEL_NAMES",
    "CHANNEL_SPECS",
    "ChannelSpec",
    "FieldSpec",
    "FormSpec",
    "StatusBranch",
    "StatusRule",
    "channel_class",
    "legacy_schema",
    "masked_field_names",
    "spec_for",
    "spec_hash",
    "spec_payload",
]

# 允许的控件形态（闭集，自洽校验用）
FIELD_TYPES: tuple[str, ...] = ("string", "password", "text_password")


@dataclass(frozen=True)
class FieldSpec:
    """单个配置字段的声明。

    `mask` 与 `password` 语义不同，**不得合并**（实测反例：`webhook_url` 在 API
    响应中被掩码，但输入控件是明文 `InputText`）：
    - `mask`：该字段在 `GET /api/notification/config` 响应中是否掩码，
      且前端提交时是否跳过掩码回显值（防掩码占位符覆盖真实凭据）；
    - `password`：输入控件是否使用密码形态（`type` 决定具体控件）。
    """

    name: str
    type: str = "string"
    label_key: str = ""
    legacy_label_key: str = ""
    label: str = ""
    required: bool = False
    mask: bool = False
    password: bool = False
    placeholder: str = ""
    placeholder_key: str = ""
    badge_key: str = ""
    divider_key: str = ""
    # 形态归属（阶段 3 · Step 2）：同一渠道可能有两种接入形态（如企微"群机器人 / 自建应用"、
    # 钉钉"webhook / 企业应用"）。空串表示"与形态无关的通用字段"（如 proxy_url）。
    # **为什么不是靠 divider_key 判断**：divider 只是展示用的分隔文案，前端无法据此做
    # "分区展示 + 互斥校验"（那是行为，不是文案）。
    form: str = ""


@dataclass(frozen=True)
class FormSpec:
    """渠道的**一种接入形态**声明（阶段 3 · Step 2：前端"按形态分区 + 互斥校验 + 参数提示"的数据源）。

    字段语义：
    · `key`：形态标识（与 `FieldSpec.form` 对应，如 `webhook` / `app`）；
    · `label_key` / `hint_key`：分区标题与**该形态的配置提示**（i18n 键，由前端渲染）；
    · `required`：该形态**可用**所需的最少字段（全非空才算"这一形态配好了"）；
    · `extra`：可选字段（填了更好，不填不影响可用）——用于提示"哪些是可选的"。
    """

    key: str
    label_key: str
    hint_key: str
    required: tuple[str, ...]
    extra: tuple[str, ...] = ()


@dataclass(frozen=True)
class StatusBranch:
    """"已配置"判定的一个分支：列出的字段全部非空即命中该分支。"""

    all_of: tuple[str, ...]
    label_key: str


@dataclass(frozen=True)
class StatusRule:
    """"已配置"判定规则：按序匹配分支，全不命中则用兜底文案键。"""

    branches: tuple[StatusBranch, ...]
    fallback_key: str


@dataclass(frozen=True)
class ChannelSpec:
    """单个渠道的声明。

    `ctor` / `ctor_required` 忠实描述 `manager._init_channels` 的**现有构造形态**：
    前者是按序传给实现类的凭证字段，后者是构造前必须非空的字段（守卫）。
    """

    name: str
    module: str
    cls_name: str
    label_key: str
    icon: str
    enabled_default: bool
    hint_key: str
    ctor: tuple[str, ...]
    ctor_required: tuple[str, ...]
    fields: tuple[FieldSpec, ...]
    status_rule: StatusRule
    # 形态声明（阶段 3 · Step 2）：供前端"按形态分区展示 + 互斥校验 + 参数提示"。
    # 单形态渠道（如 telegram）留空 ⇒ 前端按"无分区"渲染，行为与改造前一致。
    forms: tuple[FormSpec, ...] = ()


def _field_dict(f: FieldSpec) -> dict[str, Any]:
    """单个字段的前端视图（含控件形态、标签、掩码与呈现附加项）。"""
    return {
        "name": f.name,
        "type": f.type,
        "label_key": f.label_key,
        "label": f.label,
        "required": f.required,
        "mask": f.mask,
        "password": f.password,
        "placeholder": f.placeholder,
        "placeholder_key": f.placeholder_key,
        "badge_key": f.badge_key,
        "divider_key": f.divider_key,
        # 形态归属（阶段 3 · Step 2）；空串＝与形态无关的通用字段（前端归入"通用"区）
        "form": f.form,
    }


def _channel_dict(spec: ChannelSpec) -> dict[str, Any]:
    """单个渠道的前端视图（键序固定，保证响应稳定可比对）。

    **阶段 3 · Step 2** 增补两块（供前端"按形态分区 + 互斥校验 + 参数提示"）：
    · 每个字段带 `form`（空串＝与形态无关的通用字段）；
    · `forms` 按声明序给出各形态的标题/提示/必需与可选字段（单形态渠道为空列表）。
    两者都是**声明**，不含任何凭证值。
    """
    return {
        "name": spec.name,
        "label_key": spec.label_key,
        "icon": spec.icon,
        "enabled_default": spec.enabled_default,
        "hint_key": spec.hint_key,
        "fields": [_field_dict(f) for f in spec.fields],
        "forms": [
            {
                "key": f.key,
                "label_key": f.label_key,
                "hint_key": f.hint_key,
                "required": list(f.required),
                "extra": list(f.extra),
            }
            for f in spec.forms
        ],
        "status_rule": {
            "branches": [
                {"all_of": list(b.all_of), "label_key": b.label_key} for b in spec.status_rule.branches
            ],
            "fallback_key": spec.status_rule.fallback_key,
        },
    }


def spec_payload() -> dict[str, Any]:
    """产出渠道元数据负载（**不含 `spec_hash`**——哈希正是对本体计算的）。

    与 `CHANNEL_SPECS` 同序，故响应键序稳定；负载中不含任何凭证值。

    **层级结构签名（2026-10-05 阶段 4 · P6 · 4b，用户裁定"扩 spec_hash"）**：
    负载额外携带"通知层级结构"两块——
      · `notify_events`：订阅类别层的 10 类（`mapping.NOTIFY_EVENTS`）；
      · `event_class_map`：每个业务事件 → 其类别（`mapping.EVENT_MAPPINGS`）。
    为什么放进**被哈希的负载**而不是另立版本号：单一版本源（`spec_hash`）才能保证"层结构变了 ⇒ 前端缓存必失效"；
    若另立 `config_layers_version`，每加一层都要同步维护两个版本号，迟早不同步（用户裁定理由原话）。
    前端据此渲染类别层与高级层，并在 `spec_hash` 变化时重建表单（`NotificationConfig.loadChannelSpecs`）。
    """
    from ._manager_ops import notify_layers

    classes, class_map = notify_layers()
    return {
        "channels": [_channel_dict(s) for s in CHANNEL_SPECS],
        "notify_events": classes,
        "event_class_map": class_map,
    }


def spec_hash(payload: dict[str, Any]) -> str:
    """对负载做**规范化 JSON**（键排序、无多余空白）后的 SHA-256，取前 16 位。

    放在响应体而非模块常量/HTTP 头：模块常量会与响应脱节，响应头易与缓存/代理语义混淆。
    后端不缓存——每次现算（微秒级），无失效遗漏。
    """
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

# ── 渠道声明（实现见 `channel_spec_data.py`；**延迟导入**以解开与本模块的循环引用）──
# 该模块同时提供派生视图与查询函数；在此**全部再导出** ⇒ 对外 API 与拆分前完全一致
# （`from .channel_spec import CHANNEL_SPECS / spec_for / channel_class / …` 继续可用）。
from .channel_spec_data import (  # noqa: E402  （必须在数据类定义之后导入）
    CHANNEL_NAMES,
    CHANNEL_SPECS,
    channel_class,
    legacy_schema,
    masked_field_names,
    spec_for,
)
