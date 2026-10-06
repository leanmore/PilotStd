"""渠道声明数据（阶段 3 · Step 4 ③ 拆分；从 `channel_spec.py` 迁出以守 G-010）。

**为什么放在单独模块**：`CHANNEL_SPECS` 是纯声明（4 个渠道 × 字段/形态/状态规则），体量大且与
"解析/载荷/哈希"逻辑无关；混在一个文件里会让 `channel_spec.py` 越过 G-010 的 500 有效行上限。

**导入方向**：本模块 `from .channel_spec import …` 取数据类；`channel_spec.py` 在**文件末尾**再导入
本模块的 `CHANNEL_SPECS`（延迟导入）⇒ 无循环问题，且对外 API 不变
（`from .channel_spec import CHANNEL_SPECS` 继续可用）。
"""

from __future__ import annotations

from typing import Any, Callable

from .channel_spec import ChannelSpec, FieldSpec, FormSpec, StatusBranch, StatusRule

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
        # 构造顺序**必须与 `WechatChannel.__init__` 的签名一致**（`manager._init_channels` 按序位置传参）：
        # (webhook_url, corpid, agentid, corpsecret, proxy_url, touser)
        ctor=("webhook_url", "corpid", "agentid", "corpsecret", "proxy_url", "touser"),
        # 现在两种形态都**真正实现了**（阶段 3 · Step 4 ①）：webhook 走 markdown、应用形态走模板卡片
        # ⇒ 不再有"单字段必需"；可用性由 `forms` / `status_rule` 判定。
        ctor_required=(),
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
                form="webhook",
            ),
            FieldSpec(
                name="corpid",
                type="string",
                label_key="notification.config.wechat.corpid",
                placeholder="ww...",
                badge_key="notification.config.optional",
                divider_key="notification.config.wechat.app_sep",
                form="app",
            ),
            FieldSpec(
                name="agentid",
                type="string",
                label_key="notification.config.wechat.agentid",
                placeholder="1000001",
                badge_key="notification.config.optional",
                form="app",
            ),
            FieldSpec(
                name="corpsecret",
                type="text_password",
                label_key="notification.config.wechat.corpsecret",
                badge_key="notification.config.optional",
                mask=True,
                password=True,
                placeholder="...",
                form="app",
            ),
            FieldSpec(
                name="proxy_url",
                type="string",
                label_key="notification.config.wechat.proxy_url",
                placeholder="http://proxy:8080",
                badge_key="notification.config.optional",
            ),
            FieldSpec(
                name="touser",
                type="string",
                label_key="notification.config.wechat.touser",
                placeholder="@all",
                badge_key="notification.config.optional",
                form="app",
            ),
        ),
        forms=(
            # 两形态**二选一**；两者都配好时后端按 status_rule 的**分支顺序**优先自建应用
            # ⇒ 前端的提示语必须与之一致（不能让用户以为"两个都会发"）。
            FormSpec(
                key="webhook",
                label_key="notification.config.form.webhook",
                hint_key="notification.config.form.webhook_hint",
                required=("webhook_url",),
            ),
            FormSpec(
                key="app",
                label_key="notification.config.form.app",
                hint_key="notification.config.form.app_hint",
                required=("corpid", "agentid", "corpsecret"),
                extra=("touser", "proxy_url"),
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
                form="webhook",
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
                form="webhook",
            ),
            # ── 企业级互动卡片形态（阶段 S；方案 A1：新增而非替换）──
            FieldSpec(
                name="app_key",
                type="password",
                label_key="notification.config.dingtalk.app_key_label",
                badge_key="notification.config.optional_short",
                mask=True,
                password=True,
                form="app",
            ),
            FieldSpec(
                name="app_secret",
                type="password",
                label_key="notification.config.dingtalk.app_secret_label",
                badge_key="notification.config.optional_short",
                mask=True,
                password=True,
                form="app",
            ),
            FieldSpec(
                name="robot_code",
                type="string",
                label_key="notification.config.dingtalk.robot_code_label",
                badge_key="notification.config.optional_short",
                form="app",
            ),
            FieldSpec(
                name="card_template_id",
                type="string",
                label_key="notification.config.dingtalk.card_template_id_label",
                badge_key="notification.config.optional_short",
                form="app",
            ),
            # 投递目标：企业级形态必须有群会话锚点（方案 A1 的 4 个凭证之外的必要项，
            # 旧形态的等价物是 webhook_url 自身——见提交说明的差异披露）
            FieldSpec(
                name="open_conversation_id",
                type="string",
                label_key="notification.config.dingtalk.open_conversation_id_label",
                badge_key="notification.config.optional_short",
                form="app",
            ),
        ),
        forms=(
            # 两形态**二选一**；都配好时后端按 status_rule 分支顺序**优先企业级形态**（与双读一致）
            FormSpec(
                key="webhook",
                label_key="notification.config.form.webhook",
                hint_key="notification.config.form.webhook_hint",
                required=("webhook_url",),
                extra=("secret",),
            ),
            FormSpec(
                key="app",
                label_key="notification.config.form.app",
                hint_key="notification.config.form.app_hint",
                required=(
                    "app_key",
                    "app_secret",
                    "robot_code",
                    "card_template_id",
                    "open_conversation_id",
                ),
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
    # 飞书：**两种形态**（阶段 3 · Step 4 ③）——机器人 Webhook（可发卡片、**不能编辑**）与
    # 企业自建应用（留存 `message_id` ⇒ 可 `PATCH` 编辑已发消息）。
    ChannelSpec(
        name="feishu",
        module="feishu",
        cls_name="FeishuChannel",
        label_key="notification.channel.feishu",
        icon="pi pi-book",
        enabled_default=False,
        hint_key="",
        # 顺序与 `FeishuChannel.__init__` 严格一致：
        # (webhook_url, secret, app_id, app_secret, receive_id, receive_id_type)
        ctor=("webhook_url", "secret", "app_id", "app_secret", "receive_id", "receive_id_type"),
        ctor_required=(),
        fields=(
            FieldSpec(
                name="webhook_url",
                type="string",
                label="Webhook URL",
                required=False,
                mask=True,
                password=False,
                placeholder="https://open.feishu.cn/...",
                form="webhook",
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
                form="webhook",
            ),
            FieldSpec(
                name="app_id",
                type="string",
                label_key="notification.config.feishu.app_id",
                badge_key="notification.config.optional_short",
                placeholder="cli_...",
                form="app",
            ),
            FieldSpec(
                name="app_secret",
                type="password",
                label_key="notification.config.feishu.app_secret",
                badge_key="notification.config.optional_short",
                mask=True,
                password=True,
                form="app",
            ),
            FieldSpec(
                name="receive_id",
                type="string",
                label_key="notification.config.feishu.receive_id",
                badge_key="notification.config.optional_short",
                placeholder="ou_... / on_... / oc_...",
                form="app",
            ),
            FieldSpec(
                name="receive_id_type",
                type="string",
                label_key="notification.config.feishu.receive_id_type",
                badge_key="notification.config.optional_short",
                placeholder="open_id",
                form="app",
            ),
        ),
        forms=(
            # 两形态二选一；都配好时按 `status_rule` 分支序**优先应用形态**（与前端提示同源）
            FormSpec(
                key="webhook",
                label_key="notification.config.form.webhook",
                hint_key="notification.config.form.webhook_hint",
                required=("webhook_url",),
                extra=("secret",),
            ),
            FormSpec(
                key="app",
                label_key="notification.config.form.app",
                hint_key="notification.config.form.app_hint",
                required=("app_id", "app_secret", "receive_id"),
                extra=("receive_id_type",),
            ),
        ),
        status_rule=StatusRule(
            branches=(
                # 应用形态优先（与读侧一致：配了应用就走应用端点，因为它能留存 message_id 供编辑）
                StatusBranch(
                    all_of=("app_id", "app_secret", "receive_id"),
                    label_key="notification.config.status.app_message",
                ),
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
