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
from typing import Any, Callable

__all__ = [
    "CHANNEL_NAMES",
    "CHANNEL_SPECS",
    "ChannelSpec",
    "FieldSpec",
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


# ── 渠道声明 ──────────────────────────────────────────────────────────────────
# 顺序沿用既有白名单顺序，避免配置接口的响应键序发生漂移。
# 每个渠道内的字段顺序即前端表单的渲染顺序，改动需同步视觉验收。
CHANNEL_SPECS: tuple[ChannelSpec, ...] = (
    # 企业微信：群机器人与自建应用两条路径二选一，故必填标记全为否；
    # 掩码与密码形态不一致——网页地址掩码但用明文控件，应用密钥掩码且用密码控件。
    ChannelSpec(
        name="wechat",
        module="wechat",
        cls_name="WechatChannel",
        label_key="notification.channel.wechat",
        icon="pi pi-comments",
        enabled_default=True,
        hint_key="notification.config.wechat.hint",
        ctor=("webhook_url",),
        ctor_required=("webhook_url",),
        fields=(
            FieldSpec(
                name="webhook_url",
                type="string",
                label="Webhook URL",
                required=False,
                mask=True,
                password=False,
                placeholder="https://qyapi.weixin.qq.com/...",
                badge_key="notification.config.wechat.group_robot_badge",
            ),
            FieldSpec(
                name="corpid",
                type="string",
                label_key="notification.config.wechat.corpid",
                placeholder="ww...",
                badge_key="notification.config.optional",
                divider_key="notification.config.wechat.app_sep",
            ),
            FieldSpec(
                name="agentid",
                type="string",
                label_key="notification.config.wechat.agentid",
                placeholder="1000001",
                badge_key="notification.config.optional",
            ),
            FieldSpec(
                name="corpsecret",
                type="text_password",
                label_key="notification.config.wechat.corpsecret",
                badge_key="notification.config.optional",
                mask=True,
                password=True,
                placeholder="...",
            ),
            FieldSpec(
                name="proxy_url",
                type="string",
                label_key="notification.config.wechat.proxy_url",
                placeholder="http://proxy:8080",
                badge_key="notification.config.optional",
            ),
        ),
        status_rule=StatusRule(
            branches=(
                StatusBranch(
                    all_of=("corpid", "agentid", "corpsecret"),
                    label_key="notification.config.status.app_message",
                ),
                StatusBranch(
                    all_of=("webhook_url",),
                    label_key="notification.config.status.group_robot",
                ),
            ),
            fallback_key="notification.config.status.pending",
        ),
    ),
    # 钉钉：网页地址必填，加签密钥可选（不加签时留空即可）。
    ChannelSpec(
        name="dingtalk",
        module="dingtalk",
        cls_name="DingTalkChannel",
        label_key="notification.channel.dingtalk",
        icon="pi pi-bolt",
        enabled_default=False,
        hint_key="",
        # 双读（方案 A2）：新字段齐全走企业级形态，否则回落旧群机器人；两者都配时新优先。
        # ctor_required 为空是**有意**的：两种形态各自完整即可，没有单个字段是必需的。
        ctor=(
            "webhook_url",
            "secret",
            "app_key",
            "app_secret",
            "robot_code",
            "card_template_id",
            "open_conversation_id",
        ),
        ctor_required=(),
        fields=(
            FieldSpec(
                name="webhook_url",
                type="string",
                label="Webhook URL",
                required=True,
                mask=True,
                password=False,
                placeholder="https://oapi.dingtalk.com/robot/...",
            ),
            FieldSpec(
                name="secret",
                type="password",
                label_key="notification.config.dingtalk.secret_label",
                badge_key="notification.config.optional_short",
                legacy_label_key="notification.channel.config.secret",
                mask=True,
                password=True,
                placeholder="SEC...",
            ),
            # ── 企业级互动卡片形态（阶段 S；方案 A1：新增而非替换）──
            FieldSpec(
                name="app_key",
                type="password",
                label_key="notification.config.dingtalk.app_key_label",
                badge_key="notification.config.optional_short",
                mask=True,
                password=True,
            ),
            FieldSpec(
                name="app_secret",
                type="password",
                label_key="notification.config.dingtalk.app_secret_label",
                badge_key="notification.config.optional_short",
                mask=True,
                password=True,
            ),
            FieldSpec(
                name="robot_code",
                type="string",
                label_key="notification.config.dingtalk.robot_code_label",
                badge_key="notification.config.optional_short",
            ),
            FieldSpec(
                name="card_template_id",
                type="string",
                label_key="notification.config.dingtalk.card_template_id_label",
                badge_key="notification.config.optional_short",
            ),
            # 投递目标：企业级形态必须有群会话锚点（方案 A1 的 4 个凭证之外的必要项，
            # 旧形态的等价物是 webhook_url 自身——见提交说明的差异披露）
            FieldSpec(
                name="open_conversation_id",
                type="string",
                label_key="notification.config.dingtalk.open_conversation_id_label",
                badge_key="notification.config.optional_short",
            ),
        ),
        status_rule=StatusRule(
            branches=(
                # 企业级形态优先（与双读优先级一致）
                StatusBranch(
                    all_of=("app_key", "app_secret", "robot_code", "card_template_id", "open_conversation_id"),
                    label_key="notification.config.status.app_message",
                ),
                StatusBranch(all_of=("webhook_url",), label_key="notification.config.status.group_robot"),
            ),
            fallback_key="notification.config.status.pending",
        ),
    ),
    # 飞书：网页地址必填，校验密钥可选；提示文案来自前端语言包。
    ChannelSpec(
        name="feishu",
        module="feishu",
        cls_name="FeishuChannel",
        label_key="notification.channel.feishu",
        icon="pi pi-book",
        enabled_default=False,
        hint_key="",
        ctor=("webhook_url", "secret"),
        ctor_required=("webhook_url",),
        fields=(
            FieldSpec(
                name="webhook_url",
                type="string",
                label="Webhook URL",
                required=True,
                mask=True,
                password=False,
                placeholder="https://open.feishu.cn/...",
            ),
            FieldSpec(
                name="secret",
                type="password",
                label_key="notification.config.feishu.secret_label",
                badge_key="notification.config.optional_short",
                legacy_label_key="notification.channel.config.secret",
                mask=True,
                password=True,
                placeholder_key="notification.config.feishu.secret_placeholder",
            ),
        ),
        status_rule=StatusRule(
            branches=(
                StatusBranch(all_of=("webhook_url",), label_key="notification.config.status.configured"),
            ),
            fallback_key="notification.config.status.pending",
        ),
    ),
    # 电报：令牌与会话标识必须同时具备才允许构造，故两者都是构造守卫。
    ChannelSpec(
        name="telegram",
        module="telegram",
        cls_name="TelegramChannel",
        label_key="notification.channel.telegram",
        icon="pi pi-send",
        enabled_default=False,
        hint_key="",
        ctor=("bot_token", "chat_id"),
        ctor_required=("bot_token", "chat_id"),
        fields=(
            FieldSpec(
                name="bot_token",
                type="password",
                label="Bot Token",
                required=True,
                mask=True,
                password=True,
                placeholder="123456:ABC-DEF",
            ),
            FieldSpec(
                name="chat_id",
                type="string",
                label="Chat ID",
                required=True,
                mask=False,
                password=False,
                placeholder="-1001234567890",
            ),
        ),
        status_rule=StatusRule(
            branches=(
                StatusBranch(
                    all_of=("bot_token", "chat_id"),
                    label_key="notification.config.status.configured",
                ),
            ),
            fallback_key="notification.config.status.pending",
        ),
    ),
)

# 派生视图：渠道键元组的唯一声明源仍是上面的声明表，本行不构成第二份数据。
CHANNEL_NAMES: tuple[str, ...] = tuple(s.name for s in CHANNEL_SPECS)


def spec_for(name: str) -> ChannelSpec:
    """按渠道键取声明；未知渠道抛键错误（调用方应先用渠道键元组校验）。"""
    for spec in CHANNEL_SPECS:
        if spec.name == name:
            return spec
    raise KeyError(name)


def channel_class(spec: ChannelSpec) -> Any:
    """按声明解析渠道实现类（运行期 import，避免模块级导入环）。"""
    import importlib

    module = importlib.import_module(f".channels.{spec.module}", __package__)
    return getattr(module, spec.cls_name)


def masked_field_names() -> frozenset[str]:
    """全部渠道中需要掩码的字段名集合（`docker/api` 的掩码判定用）。"""
    return frozenset(f.name for s in CHANNEL_SPECS for f in s.fields if f.mask)


def legacy_schema(spec: ChannelSpec, labeler: Callable[[str], str]) -> dict[str, Any]:
    """产出既有 `get_config_schema()` 的兼容形状（`{字段: {type,label,required,secret}}`）。

    `label` 取值优先级：后端键的译文 → 字面量 → 字段名。
    """
    out: dict[str, Any] = {}
    for f in spec.fields:
        if f.legacy_label_key:
            label = labeler(f.legacy_label_key)
        else:
            label = f.label or f.name
        out[f.name] = {
            "type": f.type,
            "label": label,
            "required": f.required,
            "secret": f.password,
        }
    return out


# ── 前端元数据接口（`GET /api/notification/channels` 的响应体）──────────────────
# 只暴露**前端渲染需要**的字段。以下后端专用项**刻意不出现**在负载里：
#   `module`/`cls_name`（实现位置）、`ctor`/`ctor_required`（构造形态）、
#   `legacy_label_key`（后端兼容形状用）。新增 spec 字段时须同时决定"是否给前端"——
#   默认不给，确认前端要消费才加进本函数。


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
    }


def _channel_dict(spec: ChannelSpec) -> dict[str, Any]:
    """单个渠道的前端视图（键序固定，保证响应稳定可比对）。"""
    return {
        "name": spec.name,
        "label_key": spec.label_key,
        "icon": spec.icon,
        "enabled_default": spec.enabled_default,
        "hint_key": spec.hint_key,
        "fields": [_field_dict(f) for f in spec.fields],
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
    from .mapping import EVENT_MAPPINGS, NOTIFY_EVENTS

    return {
        "channels": [_channel_dict(s) for s in CHANNEL_SPECS],
        "notify_events": list(NOTIFY_EVENTS),
        "event_class_map": {
            key: entry.notify_event for key, entry in sorted(EVENT_MAPPINGS.items())
        },
    }


def spec_hash(payload: dict[str, Any]) -> str:
    """对负载做**规范化 JSON**（键排序、无多余空白）后的 SHA-256，取前 16 位。

    放在响应体而非模块常量/HTTP 头：模块常量会与响应脱节，响应头易与缓存/代理语义混淆。
    后端不缓存——每次现算（微秒级），无失效遗漏。
    """
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
