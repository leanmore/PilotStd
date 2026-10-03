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
                divider_key="notification.config.wechat.app_sep",
            ),
            FieldSpec(
                name="agentid",
                type="string",
                label_key="notification.config.wechat.agentid",
                placeholder="1000001",
            ),
            FieldSpec(
                name="corpsecret",
                type="text_password",
                label_key="notification.config.wechat.corpsecret",
                mask=True,
                password=True,
                placeholder="...",
            ),
            FieldSpec(
                name="proxy_url",
                type="string",
                label_key="notification.config.wechat.proxy_url",
                placeholder="http://proxy:8080",
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
                placeholder="https://oapi.dingtalk.com/robot/...",
            ),
            FieldSpec(
                name="secret",
                type="password",
                label_key="notification.config.dingtalk.secret_label",
                legacy_label_key="notification.channel.config.secret",
                mask=True,
                password=True,
                placeholder="SEC...",
            ),
        ),
        status_rule=StatusRule(
            branches=(
                StatusBranch(all_of=("webhook_url",), label_key="notification.config.status.configured"),
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
