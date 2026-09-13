# 模块：项目/核心//__工具脚本
# 聚合格式化器—从管理器脚本拆分
from typing import Any

from pilotstd.i18n import t

# 废止类状态的数据口径（适配器/检查器写入的原始状态值）。
# 严禁用 t(...) 的展示文案参与逻辑比较：en 下 t("...abolished")="Expired"，
# 与数据里的 "废止" 永不相等，会导致废止计数与告警级别随语言漂移。
ABOLISHED_STATUS_TOKENS: frozenset[str] = frozenset({"废止", "已废止", "作废", "被代替", "过期"})


def is_abolished_status(status: str) -> bool:
    """判断状态值是否属于废止类（与当前界面语言无关）。"""
    return (status or "").strip() in ABOLISHED_STATUS_TOKENS


def translate_error_message(error: str) -> str:
    """错误信息翻译映射（C-3 + 基础系统异常扩展）：用户可见的失败原因统一口径。

    优先级：异常类型名（基础系统异常）→ 业务消息关键词（C-3 原映射）→ 默认兜底。
    - TimeoutError / ReadTimeout → 网络连接超时，请稍后重试
    - ConnectionError / ConnectionRefusedError → 无法连接到目标服务器
    - PermissionError → 权限不足，请检查系统配置
    - FileNotFoundError → 找不到指定的文件或目录
    - timed out（下载场景） → 下载超时，系统将自动重试（C-3）
    - connection refused → 服务连接失败，系统将自动重试（C-3）
    - 其余 → 系统异常已记录日志
    """
    if not error:
        return t("notification.common.error.system")
    e = error.lower()
    # 基础系统异常类型映射（异常类名精确匹配，优先于业务关键词）
    if "timeouterror" in e or "readtimeout" in e:
        return t("notification.common.error.network_timeout")
    if "connectionerror" in e or "connectionrefusederror" in e:
        return t("notification.common.error.connect_failed")
    if "permissionerror" in e or "permission denied" in e:
        return t("notification.common.error.permission")
    if "filenotfounderror" in e or "no such file" in e:
        return t("notification.common.error.file_not_found")
    # C-3 业务消息映射（下载/服务连接场景）
    if "timed out" in e or "timeout" in e:
        return t("notification.common.error.download_timeout")
    if "connection refused" in e:
        return t("notification.common.error.connection_refused")
    return t("notification.common.error.system")


def format_standard_status_changed_aggregated( _event_type: str, entries: list, count: int) -> str:
    """standard_status_changed 聚合模板：汇总统计 + 明细列表。"""
    expired_count = 0
    lines: list[str] = []
    display = min(count, 10)
    for i in range(display):
        msg, _ch, _ts = entries[i]
        new_status = getattr(msg, "new_status", "") or ""
        if is_abolished_status(new_status):
            expired_count += 1
        std_no = msg.standard_number or ""
        std_name = getattr(msg, "standard_name", "") or ""
        old_status = getattr(msg, "old_status", "") or ""
        line = f"- {std_no}"
        if std_name:
            line += t("notification.aggregated.status.name_suffix").format(name=std_name)
        line += t("notification.aggregated.status.change_line").format(old=old_status, new=new_status)
        changed_at = (getattr(msg, "changed_at", "") or "")[:16]
        if changed_at:
            line += t("notification.aggregated.status.time_suffix").format(
                time=changed_at.replace("T", " ")
            )
        lines.append(line)
    if count > 10:
        for i in range(10, count):
            _msg, _ch, _ts = entries[i]
            if is_abolished_status(getattr(_msg, "new_status", "") or ""):
                expired_count += 1
    if expired_count > 0:
        header = t("notification.aggregated.status.header_with_expired").format(
            count=count, n=expired_count
        )
    else:
        header = t("notification.aggregated.status.header").format(count=count)
    body = header + "\n" + "\n".join(lines)
    if count > 10:
        body += "\n" + t("notification.aggregated.status.and_more").format(n=count - 10)
    return body


def do_test_send(
    mgr,
    channel: str,
    message: Any,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """测试发送到指定渠道。params 可覆盖 DB 中的渠道参数（如临时 webhook_url）。

    F-03 统一凭证源：渠道凭证一律从 user_credentials 表（DB）读取，
    与事件路径（_init_channels）同源；config.json 不再作为运行时凭证源。
    """
    from .manager import _CHANNEL_CLASSES  # noqa: F811
    override = params or {}
    # 先查缓存：命中时渠道已由事件路径 _init_channels 从 DB 初始化（凭证即 DB 源），
    # 与下方回退分支同源，非"双源"；回退仅在缓存未命中时执行
    ch = mgr._channels.get(channel)
    if ch is None:
        # 尝试实时初始化（优先使用中的参数）
        cls = _CHANNEL_CLASSES.get(channel)
        if cls is None:
            return {"ok": False, "error": t("notification.channel_test.unknown_channel").format(ch=channel)}
        try:
            # F-03 统一凭证源：从 DB（user_credentials）读取，CredentialHelper 不可用时报错
            # （不回退 config.json，避免重新引入双源不一致）
            if mgr._cred_helper is None:
                return {"ok": False, "error": "credential_helper_unavailable"}
            creds: dict[str, str] = mgr._cred_helper.get_channel(mgr._user_id, channel) or {}
            if channel == "telegram":
                token = (
                    override.get("bot_token") or creds.get("bot_token") or ""
                ).strip()
                chat_id = (
                    override.get("chat_id") or creds.get("chat_id") or ""
                ).strip()
                if not token:
                    return {"ok": False, "error": t("notification.channel_test.missing_bot_token")}
                if not chat_id:
                    return {"ok": False, "error": t("notification.channel_test.missing_chat_id")}
                ch = cls(token, chat_id)
            elif channel == "dingtalk":
                url = override.get("webhook_url") or creds.get("webhook_url") or ""
                secret = override.get("secret") or creds.get("secret") or ""
                if not url:
                    return {"ok": False, "error": t("notification.channel_test.missing_dingtalk_webhook")}
                ch = cls(url, secret)
            elif channel == "feishu":
                url = override.get("webhook_url") or creds.get("webhook_url") or ""
                secret = override.get("secret") or creds.get("secret") or ""
                if not url:
                    return {"ok": False, "error": t("notification.channel_test.missing_feishu_webhook")}
                ch = cls(url, secret)
            elif channel == "wechat":
                # 企业微信：优先应用消息（corpid+agentid+corpsecret），其次群机器人（webhook_url）
                corpid = override.get("corpid") or creds.get("corpid") or ""
                agentid = override.get("agentid") or creds.get("agentid") or ""
                corpsecret = override.get("corpsecret") or creds.get("corpsecret") or ""
                if corpid and agentid and corpsecret:
                    # 应用消息模式 — 需特殊初始化
                    ch = cls(corpid, agentid, corpsecret)
                else:
                    url = override.get("webhook_url") or creds.get("webhook_url") or ""
                    if not url:
                        return {
                            "ok": False,
                            "error": t("notification.channel_test.missing_wechat_url"),
                        }
                    ch = cls(url)
            else:
                url = override.get("webhook_url") or creds.get("webhook_url") or ""
                if not url:
                    return {
                        "ok": False,
                        "error": t("notification.channel_test.missing_webhook").format(ch=channel),
                    }
                ch = cls(url)
        except Exception as e:
            return {
                "ok": False,
                "error": t("notification.channel_test.init_failed").format(e=e),
            }
    try:
        ok = ch.send(message)
        return {"ok": ok, "error": "" if ok else t("notification.channel_test.send_failed")}
    except Exception as e:
        return {"ok": False, "error": str(e)}
