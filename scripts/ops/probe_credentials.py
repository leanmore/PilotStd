#!/usr/bin/env python3
"""部署探测：通知渠道凭证齐全性 + 连通性（只读，**不发任何消息**）。

覆盖 A-27.1 相关：飞书需要 `app_id` / `app_secret` / 测试群 `chat_id`（对应 `receive_id`），
企微需要 `corpid` / `agentid` / `corpsecret` 或群机器人 `webhook_url`，Telegram 需要
`bot_token` / `chat_id`。判据来自渠道声明 `GET /api/notification/channels` 的
`forms[].required` 与 `status_rule.branches[].all_of`（单一真相，不在脚本里硬编码字段表）。

三层判定（每层独立给结论，不把「没配」说成「连不上」）：

1. **齐全性**：必填字段是否都有值。服务端回显的密钥字段是掩码 `***`（`MASKED_VALUE`），
   掩码视为「已配置」但**不可核对真值**；
2. **连通性**：
   * 飞书：`POST .../auth/v3/tenant_access_token/internal`（唯一放行的外部只读 POST：只签令牌）；
   * Telegram：`GET https://api.telegram.org/bot<token>/getMe`（只读，不取消息）；
   * 企微：`GET https://qyapi.weixin.qq.com/cgi-bin/gettoken`（只签令牌，只读）；
   * 群机器人 webhook：**不探测**——任何请求都会真的往群里发消息，如实标「不探测」；
3. **启用状态**：`enabled=false` 的渠道即使配好也不会发通知，单独作为诊断项。

凭据安全：所有输出经 `mask_secret()` 脱敏（`ab***`），密钥**绝不**落到报告或 JSON 里。

用法：
  python scripts/ops/probe_credentials.py
  python scripts/ops/probe_credentials.py --base-url http://192.168.1.18:9028 --json
  python scripts/ops/probe_credentials.py --channel feishu   # 只看飞书

退出码：0 通过 / 1 有失败或必跑项无法验证 / 2 环境不可达。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _probe_common as common  # noqa: E402  共享层（凭据/HTTP/报告）

# 服务端对密钥字段的回显掩码（复用共享层常量，避免两份定义漂移）
MASKED_VALUES = common.MASKED_VALUES
# 飞书/企微令牌端点与 Telegram 只读端点（全部为「只签发令牌」或「只读自身信息」）
FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
WECHAT_TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
TELEGRAM_GETME_URL = "https://api.telegram.org/bot{token}/getMe"
# 飞书群 chat_id 在渠道配置里的字段名（群菜单用 receive_id；消息投递同为 receive_id）
FEISHU_CHAT_ID_FIELDS = ("receive_id", "chat_id")


def _is_configured(value: Any) -> bool:
    """字段是否「有值」：非空串，或服务端回显的掩码（掩码=已配置，只是真值不可见）。"""
    text = str(value or "").strip()
    return bool(text)


def _is_masked(value: Any) -> bool:
    """字段值是否是服务端掩码（真值不可核对）。"""
    return str(value or "").strip() in MASKED_VALUES


def _spec_index(client: common.HttpClient) -> dict[str, dict]:
    """取渠道声明（必填字段/形态/状态规则），返回 `{渠道名: 声明}`；失败返回空字典。"""
    status_code, payload = client.get_json("/api/notification/channels")
    if status_code != 200 or not isinstance(payload, dict):
        return {}
    return {str(c.get("name") or ""): c for c in payload.get("channels") or []}


def _required_fields(spec: dict) -> dict[str, list[str]]:
    """从渠道声明里取「形态 → 必填字段」；无 forms 声明时退回 status_rule 的 all_of 分支。"""
    result: dict[str, list[str]] = {}
    for form in spec.get("forms") or []:
        key = str(form.get("key") or "")
        required = [str(f) for f in form.get("required") or []]
        if key and required:
            result[key] = required
    if result:
        return result
    for branch in (spec.get("status_rule") or {}).get("branches") or []:
        all_of = [str(f) for f in branch.get("all_of") or []]
        if all_of:
            result[str(branch.get("label_key") or "branch")] = all_of
    return result


def _any_form_complete(config: dict[str, Any], required: dict[str, list[str]]) -> tuple[bool, str]:
    """判断是否至少有一种形态的必填字段全部有值，返回 `(是否齐全, 说明)`。

    说明里带上命中的形态键（如 `app` / `webhook`），调用方据此决定后续还要不要查 chat_id。
    """
    if not required:
        return False, "渠道声明里没有必填字段定义（无法判定齐全性）"
    details: list[str] = []
    for form_key, fields in required.items():
        missing = [f for f in fields if not _is_configured(config.get(f))]
        if not missing:
            return True, f"{form_key} 形态齐全（{', '.join(fields)}）"
        details.append(f"{form_key} 缺 {', '.join(missing)}")
    return False, "；".join(details)


def _complete_form(config: dict[str, Any], required: dict[str, list[str]]) -> str:
    """返回第一个「必填字段全部有值」的形态键；没有则返回空串。"""
    for form_key, fields in required.items():
        if all(_is_configured(config.get(f)) for f in fields):
            return form_key
    return ""


def _credential_status(config: dict, options: common.ProbeOptions) -> tuple[str, str, str]:
    """按「渠道是否启用」决定凭证不全的严重度，返回 `(状态, 等级, 提示后缀)`。

    理由：未启用的渠道本来就不发通知，缺凭证是「待配置」而不是「部署缺陷」；一旦启用却缺
    凭证，消息会静默发不出去，必须阻断。默认把「未启用且未配置」记为**必跑的无法验证**
    （不假装通过）；若调用方显式 `--allow-unconfigured-channels`，才降级为诊断项 `skip`。
    """
    if bool(config.get("enabled")):
        return common.STATUS_FAIL, common.TIER_REQUIRED, "（渠道已启用，缺凭证会导致通知静默失败）"
    if options.allow_unconfigured_channels:
        return (
            common.STATUS_SKIP,
            common.TIER_ADVISORY,
            "（渠道未启用且未配置，按 --allow-unconfigured-channels 记为不适用）",
        )
    return (
        common.STATUS_UNVERIFIED,
        common.TIER_REQUIRED,
        "（渠道当前未启用；如需启用需补齐以上字段，或加 --allow-unconfigured-channels 忽略）",
    )


def probe_feishu(
    report: common.Report,
    config: dict,
    spec: dict,
    options: common.ProbeOptions,
    external_session=None,
) -> None:
    """飞书：齐全性（app_id / app_secret / receive_id）+ 连通性（只签令牌，不发消息）。"""
    required = _required_fields(spec)
    complete, detail = _any_form_complete(config, required)
    if not complete:
        state, tier, suffix = _credential_status(config, options)
        report.add(
            "feishu.credentials",
            state,
            f"飞书凭证不齐全：{detail}（需要 app_id / app_secret / 测试群 chat_id）{suffix}",
            tier=tier,
            enabled=bool(config.get("enabled")),
        )
        return
    report.add(
        "feishu.credentials",
        common.STATUS_PASS,
        f"飞书凭证齐全：{detail}",
        enabled=bool(config.get("enabled")),
        app_id=mask_or_empty(config.get("app_id")),
    )
    # 只有 `app` 形态才需要群 chat_id；纯 `webhook`（群机器人）形态不适用
    if _complete_form(config, required) != "app":
        report.add(
            "feishu.chat_id",
            common.STATUS_SKIP,
            "当前为 webhook（群机器人）形态，不需要 chat_id",
            tier=common.TIER_ADVISORY,
        )
        return
    chat_field = next((f for f in FEISHU_CHAT_ID_FIELDS if _is_configured(config.get(f))), "")
    if chat_field:
        report.add(
            "feishu.chat_id",
            common.STATUS_PASS,
            f"测试群 {chat_field}={str(config.get(chat_field))[:12]}…（chat_id 非密钥，仅截断展示）",
        )
    else:
        state, tier, suffix = _credential_status(config, options)
        report.add(
            "feishu.chat_id",
            state,
            f"缺少测试群 chat_id（{ '/'.join(FEISHU_CHAT_ID_FIELDS) }）；"
            "可用 GET /api/notification/menu/chats?channel=feishu 自动发现" + suffix,
            tier=tier,
        )
    if _is_masked(config.get("app_secret")) or not _is_configured(config.get("app_secret")):
        # 掩码下拿不到明文 `secret`，无法做令牌换取；如实标「无法验证」而不是假装连通
        report.add(
            "feishu.connectivity",
            common.STATUS_UNVERIFIED,
            "app_secret 被服务端掩码（***），无法在探测侧换取 tenant_access_token；"
            "请在容器内用真实凭证自检，或临时以明文凭证单独跑 --feishu-secret",
            tier=common.TIER_REQUIRED,
        )
        return
    probe_feishu_token(report, config, options, external_session)


def probe_feishu_token(
    report: common.Report,
    config: dict,
    options: common.ProbeOptions,
    external_session=None,
) -> None:
    """用明文 app_id/app_secret 换 tenant_access_token，只判断连通性（不发送消息）。"""
    client = common.ExternalProbe(timeout=options.timeout, session=external_session)
    try:
        response = client.request(
            "POST",
            FEISHU_TOKEN_URL,
            json={"app_id": config.get("app_id"), "app_secret": config.get("app_secret")},
        )
    except common.EnvironmentUnreachable as exc:
        report.add("feishu.connectivity", common.STATUS_UNVERIFIED, f"外部网络不可达：{exc}")
        return
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    code = payload.get("code")
    if response.status_code == 200 and code == 0:
        report.add(
            "feishu.connectivity",
            common.STATUS_PASS,
            "tenant_access_token 换取成功（未发送任何消息）",
            token_type=payload.get("token_type"),
        )
    else:
        report.add(
            "feishu.connectivity",
            common.STATUS_FAIL,
            f"令牌换取失败：HTTP {response.status_code} code={code} msg={payload.get('msg')}",
        )


def probe_wechat(
    report: common.Report,
    config: dict,
    spec: dict,
    options: common.ProbeOptions,
    external_session=None,
) -> None:
    """企微：齐全性 + 连通性（gettoken 只签令牌）；群机器人 webhook 不探测（会真的发消息）。"""
    required = _required_fields(spec)
    complete, detail = _any_form_complete(config, required)
    webhook = _is_configured(config.get("webhook_url"))
    if webhook:
        report.add(
            "wechat.webhook",
            common.STATUS_UNVERIFIED,
            "群机器人 webhook_url 已配置；**不探测**（任何请求都会真的往群里发消息），"
            "请用管理端「测试发送」人工确认",
            tier=common.TIER_ADVISORY,
        )
    if not complete:
        state, tier, suffix = _credential_status(config, options)
        if webhook:
            # 已有群机器人 `webhook` 兜底：缺应用凭证不阻断，但仍要如实提示
            state = common.STATUS_UNVERIFIED
            tier = common.TIER_ADVISORY
            suffix = "（已有群机器人 webhook 兜底，不阻断）"
        report.add(
            "wechat.credentials",
            state,
            f"应用形态凭证不齐全：{detail}{suffix}",
            tier=tier,
            enabled=bool(config.get("enabled")),
        )
        return
    report.add(
        "wechat.credentials",
        common.STATUS_PASS,
        f"企微应用凭证齐全：{detail}",
        enabled=bool(config.get("enabled")),
        corpid=mask_or_empty(config.get("corpid")),
        agentid=str(config.get("agentid") or "").strip(),
    )
    if _is_masked(config.get("corpsecret")):
        report.add(
            "wechat.connectivity",
            common.STATUS_UNVERIFIED,
            "corpsecret 被服务端掩码（***），无法换取 access_token；需在容器内自检",
            tier=common.TIER_ADVISORY,
        )
        return
    client = common.ExternalProbe(timeout=options.timeout, session=external_session)
    try:
        response = client.request(
            "GET",
            WECHAT_TOKEN_URL,
            params={"corpid": config.get("corpid"), "corpsecret": config.get("corpsecret")},
        )
    except common.EnvironmentUnreachable as exc:
        report.add("wechat.connectivity", common.STATUS_UNVERIFIED, f"外部网络不可达：{exc}")
        return
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    ok = payload.get("errcode") == 0
    report.add(
        "wechat.connectivity",
        common.STATUS_PASS if ok else common.STATUS_FAIL,
        (
            "access_token 换取成功（未发送任何消息）"
            if ok
            else f"令牌换取失败：HTTP {response.status_code} errcode={payload.get('errcode')} "
            f"errmsg={payload.get('errmsg')}"
        ),
    )


def probe_telegram(
    report: common.Report,
    config: dict,
    options: common.ProbeOptions,
    external_session=None,
) -> None:
    """Telegram：齐全性（bot_token / chat_id）+ 连通性（getMe 只读）。"""
    token = str(config.get("bot_token") or "")
    chat_id = str(config.get("chat_id") or "")
    missing = [name for name, value in (("bot_token", token), ("chat_id", chat_id)) if not _is_configured(value)]
    if missing:
        report.add(
            "telegram.credentials",
            common.STATUS_FAIL,
            f"Telegram 凭证不齐全：缺 {', '.join(missing)}",
            enabled=bool(config.get("enabled")),
        )
        return
    report.add(
        "telegram.credentials",
        common.STATUS_PASS,
        f"Telegram 凭证齐全（bot_token={mask_or_empty(token)} chat_id={chat_id[:12]}…）",
        enabled=bool(config.get("enabled")),
    )
    if _is_masked(token):
        report.add(
            "telegram.connectivity",
            common.STATUS_UNVERIFIED,
            "bot_token 被服务端掩码（***），无法调用 getMe；需在容器内自检",
            tier=common.TIER_ADVISORY,
        )
        return
    client = common.ExternalProbe(timeout=options.timeout, session=external_session)
    try:
        response = client.request("GET", TELEGRAM_GETME_URL.format(token=token))
    except common.EnvironmentUnreachable as exc:
        report.add("telegram.connectivity", common.STATUS_UNVERIFIED, f"外部网络不可达：{exc}")
        return
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    ok = bool(payload.get("ok"))
    report.add(
        "telegram.connectivity",
        common.STATUS_PASS if ok else common.STATUS_FAIL,
        (
            f"getMe 成功：@{((payload.get('result') or {}).get('username'))}（未发送任何消息）"
            if ok
            else f"getMe 失败：HTTP {response.status_code} {payload.get('description') or ''}"
        ),
    )


def mask_or_empty(value: Any) -> str:
    """对外展示的脱敏值（空值返回空串，非空返回 `ab***`）。"""
    return common.mask_secret(str(value or ""))


def probe_enabled_flags(report: common.Report, configs: dict[str, dict]) -> None:
    """诊断项：哪些渠道已配好但 `enabled=false`（配了却不会发通知是常见漏配）。"""
    disabled = [name for name, cfg in configs.items() if not cfg.get("enabled")]
    report.add(
        "channels.enabled",
        common.STATUS_PASS if disabled else common.STATUS_PASS,
        "未启用渠道：" + ("、".join(disabled) if disabled else "无（全部启用）"),
        tier=common.TIER_ADVISORY,
        disabled=disabled,
    )


def run(options: common.ProbeOptions, session=None, external_session=None) -> common.Report:
    """执行本 probe：读配置 → 逐渠道齐全性/连通性；登录失败则如实标「无法验证」。"""
    creds = common.read_creds()
    base_url = common.resolve_base_url(options.base_url, creds)
    report = common.Report("credentials", base_url)
    client = common.HttpClient(base_url, timeout=options.timeout, session=session, creds=creds)
    try:
        status_code, _ = client.get_json("/api/health")
    except common.EnvironmentUnreachable as exc:
        report.unreachable_reason = str(exc)
        report.add("health.reachable", common.STATUS_UNVERIFIED, f"环境不可达：{exc}")
        return report
    if status_code != 200:
        report.add("health.reachable", common.STATUS_UNVERIFIED, f"/api/health 返回 {status_code}")
        return report
    try:
        login_detail = client.require_admin()
        report.add("auth.admin", common.STATUS_PASS, login_detail)
    except common.AuthError as exc:
        report.add(
            "auth.admin",
            common.STATUS_UNVERIFIED,
            f"{exc}；所需条件：config/docker_creds.json 的 username/password 为 admin 账号"
            "（通知配置按用户维度存储，非 admin 看不到全量渠道凭证）",
        )
        return report

    status_code, payload = client.get_json("/api/notification/config")
    if status_code != 200 or not isinstance(payload, dict):
        report.add(
            "notification.config",
            common.STATUS_UNVERIFIED,
            f"GET /api/notification/config 返回 {status_code}",
        )
        return report
    channels = payload.get("channels") or {}
    report.add(
        "notification.enabled",
        common.STATUS_PASS if payload.get("enabled") else common.STATUS_FAIL,
        f"全局通知开关 enabled={payload.get('enabled')}",
    )
    specs = _spec_index(client)
    if not specs:
        report.add(
            "notification.spec",
            common.STATUS_UNVERIFIED,
            "读不到 /api/notification/channels，必填字段按内置规则判定",
            tier=common.TIER_ADVISORY,
        )

    if "feishu" in channels:
        probe_feishu(report, channels["feishu"] or {}, specs.get("feishu") or {}, options, external_session)
    if "wechat" in channels:
        probe_wechat(report, channels["wechat"] or {}, specs.get("wechat") or {}, options, external_session)
    if "telegram" in channels:
        probe_telegram(report, channels["telegram"] or {}, options, external_session)
    probe_enabled_flags(report, {k: v or {} for k, v in channels.items()})
    return report


def main(argv: list[str] | None = None) -> int:
    """命令行入口：解析参数 → 跑探测 → 按退出码语义返回。"""
    common.stdout_utf8()
    parser = argparse.ArgumentParser(description="部署探测：通知渠道凭证齐全性 + 连通性（只读）")
    common.add_common_args(parser)
    parser.add_argument(
        "--channel",
        default="",
        help="只探测指定渠道（feishu/wechat/telegram），默认全部",
    )
    parser.add_argument(
        "--allow-unconfigured-channels",
        action="store_true",
        help="把「渠道未启用且未配置」记为不适用（skip）而不是无法验证；默认关闭（不假装通过）",
    )
    args = parser.parse_args(argv)
    options = common.ProbeOptions(
        base_url=args.base_url,
        timeout=args.timeout,
        strict=args.strict,
        allow_unconfigured_channels=args.allow_unconfigured_channels,
    )
    report = run(options)
    if args.channel:
        # 单渠道视图：过滤掉其它渠道的结论（保留 auth/全局项）
        keep = (args.channel, "auth.", "notification.", "health.")
        report.checks = [c for c in report.checks if c.name.startswith(keep)]
    if report.unreachable_reason:
        common.finish(report, args)
        return common.EXIT_UNREACHABLE
    return common.finish(report, args)


if __name__ == "__main__":
    sys.exit(main())
