# 模块：项目/核心//__工具脚本
# 聚合格式化器—从管理器脚本拆分
from typing import Any

from pilotstd.i18n import _


def format_standard_status_changed_aggregated( _event_type: str, entries: list, count: int) -> str:
    """standard_status_changed 聚合模板：汇总统计 + 明细列表。"""
    expired_count = 0
    lines: list[str] = []
    display = min(count, 10)
    for i in range(display):
        msg, _ch, _ts = entries[i]
        new_status = getattr(msg, "new_status", "") or ""
        if new_status == "废止":
            expired_count += 1
        std_no = msg.standard_number or ""
        std_name = getattr(msg, "standard_name", "") or ""
        old_status = getattr(msg, "old_status", "") or ""
        line = f"- {std_no}"
        if std_name:
            line += _("（{name}）").format(name=std_name)
        line += _("：{old} → {new}").format(old=old_status, new=new_status)
        changed_at = (getattr(msg, "changed_at", "") or "")[:16]
        if changed_at:
            line += _("，{time}").format(time=changed_at.replace("T", " "))
        lines.append(line)
    if count > 10:
        for i in range(10, count):
            _msg, _ch, _ts = entries[i]
            if (getattr(_msg, "new_status", "") or "") == "废止":
                expired_count += 1
    if expired_count > 0:
        header = _("{count} 项标准状态变更（其中 {n} 项已废止）").format(count=count, n=expired_count)
    else:
        header = _("{count} 项标准状态变更").format(count=count)
    body = header + "\n" + "\n".join(lines)
    if count > 10:
        body += "\n" + _("等 {n} 项").format(n=count - 10)
    return body


def do_test_send(
    mgr,
    channel: str,
    message: Any,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """测试发送到指定渠道。params 可覆盖配置中的渠道参数（如临时 webhook_url）。"""
    from .manager import _CHANNEL_CLASSES  # noqa: F811
    override = params or {}
    ch = mgr._channels.get(channel)
    if ch is None:
        # 尝试实时初始化（优先使用中的参数）
        cls = _CHANNEL_CLASSES.get(channel)
        if cls is None:
            return {"ok": False, "error": f"未知渠道: {channel}"}
        try:
            if channel == "telegram":
                token = (
                    override.get("bot_token") or mgr._cfg.get("notification.channels.telegram.bot_token", "")
                ).strip()
                chat_id = (
                    override.get("chat_id") or mgr._cfg.get("notification.channels.telegram.chat_id", "")
                ).strip()
                if not token:
                    return {"ok": False, "error": "缺少 bot_token"}
                if not chat_id:
                    return {"ok": False, "error": "缺少 chat_id"}
                ch = cls(token, chat_id)
            elif channel == "dingtalk":
                url = override.get("webhook_url") or mgr._cfg.get("notification.channels.dingtalk.webhook_url", "")
                secret = override.get("secret") or mgr._cfg.get("notification.channels.dingtalk.secret", "")
                if not url:
                    return {"ok": False, "error": "缺少 webhook_url（钉钉群机器人必填）"}
                ch = cls(url, secret)
            elif channel == "feishu":
                url = override.get("webhook_url") or mgr._cfg.get("notification.channels.feishu.webhook_url", "")
                secret = override.get("secret") or mgr._cfg.get("notification.channels.feishu.secret", "")
                if not url:
                    return {"ok": False, "error": "缺少 webhook_url（飞书机器人必填）"}
                ch = cls(url, secret)
            elif channel == "wechat":
                # 企业微信：优先应用消息(++)，其次群机器人(_)
                corpid = override.get("corpid") or mgr._cfg.get("notification.channels.wechat.corpid", "")
                agentid = override.get("agentid") or mgr._cfg.get("notification.channels.wechat.agentid", "")
                corpsecret = override.get("corpsecret") or mgr._cfg.get(
                    "notification.channels.wechat.corpsecret", ""
                )
                if corpid and agentid and corpsecret:
                    # 应用消息模式 — 需特殊初始化
                    ch = cls(corpid, agentid, corpsecret)
                else:
                    url = override.get("webhook_url") or mgr._cfg.get(
                        "notification.channels.wechat.webhook_url", ""
                    )
                    if not url:
                        return {
                            "ok": False,
                            "error": "缺少 webhook_url（群机器人）或 corpid+agentid+corpsecret（应用消息）",
                        }
                    ch = cls(url)
            else:
                url = override.get("webhook_url") or mgr._cfg.get(
                    f"notification.channels.{channel}.webhook_url", ""
                )
                if not url:
                    return {"ok": False, "error": f"缺少 {channel} 渠道的 webhook_url"}
                ch = cls(url)
        except Exception as e:
            return {"ok": False, "error": f"渠道初始化失败: {e}"}
    try:
        ok = ch.send(message)
        return {"ok": ok, "error": "" if ok else "发送失败"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

