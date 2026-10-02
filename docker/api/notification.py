# 容器//脚本—通知配置与发送日志接口（2：四渠道全参数）
import logging
from typing import cast

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.audit import write_audit
from pilotstd.core.notification import NotificationManager, NotificationMessage
from pilotstd.core.notification._credentials import MASKED_VALUE, CredentialHelper
from pilotstd.core.notification.events import ALL_EVENT_KEYS
from pilotstd.core.notification.security_notifier import client_ip, notify_credential_change
from pilotstd.i18n import t
from pilotstd.manager.facade import StandardManager

from ..auth import get_current_user_id
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notification"])

# SEC-001: 本模块 9 个接口移除 @require_role —— 通知是用户级功能，
# 认证由 AuthMiddleware 保证，用户间隔离通过 user_id=Depends(_get_user_id)。

# ════════════════════════════════════════════════════════════════ 分隔
# 辅助函数：用户提取+通知管理器获取
# ════════════════════════════════════════════════════════════════ 分隔


def _get_user_id(user_id: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)) -> int:
    """按主键校验用户存在性，不存在则抛出 401。"""
    if mgr.user_service.get_user_by_id(user_id) is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user_id


class MarkReadRequest(BaseModel):
    id: int | None = None  # None 表示全部标记已读


def _get_notification_mgr(mgr=Depends(get_manager_dep)) -> NotificationManager:
    return cast("NotificationManager", mgr.notification_mgr)


def _find_masked_field(body: dict, cred_helper: CredentialHelper | None) -> str:
    """预校验：返回首个掩码占位符字段的报错文案，无违规返回空串。

    掩码值会被 CredentialHelper.set_channel 整体拒绝；提前拦下可保证落库循环不抛异常、
    且告警不会为一次注定失败的请求发出（避免误报"凭证已变更"）。
    """
    if cred_helper is None:
        return ""
    masked_values: set[str] = set(getattr(cred_helper, "MASKED_VALUES", set()))
    channels = body.get("channels")
    if not isinstance(channels, dict):
        return ""
    for ch_cfg in channels.values():
        if not isinstance(ch_cfg, dict):
            continue
        for field, field_value in ch_cfg.items():
            if isinstance(field_value, str) and field_value.strip() in masked_values:
                return f"凭证校验失败: 字段 '{field}' 的值疑似掩码占位符，请重新输入真实凭证。"
    return ""


def _diff_credential_changes(
    body: dict, cred_helper: CredentialHelper | None, user_id: int
) -> tuple[dict[str, dict], dict[str, dict[str, str]], list[str], list[str]]:
    """读取待改渠道的旧凭证快照并计算差异。

    返回 ``(待写渠道配置, 旧凭证快照, 变更渠道列表, 变更字段列表)``。
    必须在 `set_channel` 落库**之前**调用：凭证为合并写入 + INSERT OR REPLACE，
    落库后旧值不可恢复，而告警必须用旧地址发送。
    差异口径沿用 `set_channel` 的合并语义——空串跳过不覆盖（不构成变更），
    `enabled` 归一化为 "true"/"false" 文本比较。
    """
    channel_updates: dict[str, dict] = {}
    channels = body.get("channels")
    if not (isinstance(channels, dict) and cred_helper is not None):
        return channel_updates, {}, [], []
    masked_values: set[str] = set(getattr(cred_helper, "MASKED_VALUES", set()))
    for ch_name, ch_cfg in channels.items():
        if isinstance(ch_cfg, dict):
            channel_updates[ch_name] = ch_cfg

    old_creds: dict[str, dict[str, str]] = {}
    changed_channels: list[str] = []
    changed_keys: list[str] = []
    for ch_name, ch_cfg in channel_updates.items():
        old = cred_helper.get_channel(user_id, ch_name) or {}
        old_creds[ch_name] = old
        for field, field_value in ch_cfg.items():
            if isinstance(field_value, str) and field_value.strip() in masked_values:
                continue
            if field == "enabled":
                if old.get(field, "") == ("true" if field_value else "false"):
                    continue
            elif isinstance(field_value, str) and field_value.strip() == "":
                continue
            elif old.get(field, "") == field_value:
                continue
            changed_channels.append(ch_name)
            if field not in changed_keys:
                changed_keys.append(field)
    return channel_updates, old_creds, changed_channels, changed_keys


@router.get("/api/notification/config")
def get_config(request: Request, mgr=Depends(get_manager_dep), user_id: int = Depends(_get_user_id)):
    """读取当前用户的渠道凭证配置。"""
    nmgr = mgr.notification_mgr
    creds: dict[str, dict[str, str]] = {}
    if nmgr._cred_helper:
        creds = nmgr._cred_helper.get_all(user_id)

    def mask(v: str) -> str:
        """掩码函数：非空值统一返回掩码占位符（引用常量，不硬编码）。"""
        return MASKED_VALUE if v else ""

    # 构建每个渠道的配置视图，敏感字段（_等）做掩码处理
    def build_channel(ch_name: str, defaults: dict) -> dict:
        """构建单个渠道的配置视图：合并用户凭证与默认参数，敏感字段做掩码处理。"""
        ch = creds.get(ch_name) or {}
        result: dict[str, object] = {}
        for k in defaults:
            val = ch.get(k, "")
            if k in ("webhook_url", "bot_token", "secret", "corpsecret"):
                result[k] = mask(str(val))
            elif k == "enabled":
                if isinstance(val, bool):
                    result[k] = val
                elif isinstance(val, str) and val.lower() in ("false", "0", ""):
                    result[k] = False
                else:
                    result[k] = bool(val)
            else:
                result[k] = str(val)
        return result

    return {
        "enabled": nmgr.enabled,
        # 四渠道配置：///
        "channels": {
            "wechat": build_channel(
                "wechat",
                {
                    "enabled": True,
                    "webhook_url": "",
                    "corpid": "",
                    "agentid": "",
                    "corpsecret": "",
                    "proxy_url": "",
                },
            ),
            "telegram": build_channel("telegram", {"enabled": False, "bot_token": "", "chat_id": ""}),
            "feishu": build_channel("feishu", {"enabled": False, "webhook_url": "", "secret": ""}),
            "dingtalk": build_channel("dingtalk", {"enabled": False, "webhook_url": "", "secret": ""}),
        },
        "rules": {ev: mgr.cfg.get(f"notification.rules.{ev}", []) for ev in ALL_EVENT_KEYS},
    }


@router.put("/api/notification/config")
def update_config(
    request: Request,
    body: dict,
    mgr=Depends(get_manager_dep),
    user_id: int = Depends(_get_user_id),
):
    """更新通知配置（按用户隔离）。

    凭证变更的安全顺序（第 2 批安全审计闭环，见 docs/plans/batch2-security-audit-design.md）：
    E2 读旧凭证 → E3 预校验 → E4 **先向旧渠道发告警** → E5 才落库 → E9 审计。
    顺序不可调换：凭证落库后，旧 webhook 地址即不可恢复（合并写入 + INSERT OR REPLACE），
    而告警若晚于落库就会投递到新地址——正是要防的攻击场景。
    """
    nmgr = mgr.notification_mgr
    user_id_int = int(user_id)
    # 防御式取来源地址：测试替身（MagicMock）的属性访问会返回 Mock，
    # 直接放进审计 detail 会让 json.dumps 崩溃；只用于审计展示，取不到就留空。
    from_ip = client_ip(request)
    warnings: list[str] = []

    # ── E3 预校验 → E2 读旧凭证快照 + 差异计算（均在任何写入之前）──
    masked_error = _find_masked_field(body, nmgr._cred_helper)
    if masked_error:
        # 预校验失败也写审计（L2 出口覆盖）：请求载荷含**掩码占位符**（客户端回传了
        # `****` 形式的旧值）说明前端状态失真或有人在构造异常请求——失败尝试是比
        # 成功操作更有价值的信号。**只记字段名，绝不记凭证值**（与下方成功分支同口径）。
        write_audit(
            action="NOTIFICATION_CREDENTIAL_CHANGE_REJECTED",
            resource="PUT /api/notification/config",
            detail={"user_id": user_id_int, "from_ip": from_ip, "reason": masked_error},
            user_id=user_id_int,
        )
        return JSONResponse({"error": masked_error}, status_code=400)
    channel_updates, old_creds, changed_channels, changed_keys = _diff_credential_changes(
        body, nmgr._cred_helper, user_id_int
    )

    # enabled / rules 的变更判定同样前置：幂等保存（值未变）不应产生告警与审计噪声
    enabled_changed = "enabled" in body and bool(body["enabled"]) != bool(
        mgr.cfg.get("notification.enabled", False)
    )
    rules_changed = False
    if "rules" in body and isinstance(body["rules"], dict):
        for rule_name, channels in body["rules"].items():
            if mgr.cfg.get(f"notification.rules.{rule_name}") != channels:
                rules_changed = True
                break

    # ── E4 先通知旧渠道（使用 E2 的旧凭证快照；绝不走 manager.send_event）──
    if changed_channels or rules_changed or enabled_changed:
        sent, failed = notify_credential_change(
            notification_mgr=nmgr,
            cred_helper=nmgr._cred_helper,
            user_id=user_id_int,
            changed_channels=changed_channels,
            old_creds=old_creds,
            changed_keys=changed_keys,
            rules_changed=rules_changed,
            enabled_changed=enabled_changed,
            from_ip=from_ip,
        )
        if failed:
            warnings.append(t("notification.api.credential_notify_failed").format(channels=", ".join(failed)))
        elif not sent and changed_channels:
            warnings.append(t("notification.api.credential_notify_no_channel"))

    # ── E5 落库 + E9 审计（凭证告警已在 E4 完成，此处顺序不可前移）──
    write_error = _persist_config_and_audit(
        mgr=mgr,
        nmgr=nmgr,
        body=body,
        user_id=user_id,
        user_id_int=user_id_int,
        changed_channels=changed_channels,
        changed_keys=changed_keys,
        enabled_changed=enabled_changed,
        rules_changed=rules_changed,
        from_ip=from_ip,
        warnings=warnings,
    )
    if write_error is not None:
        return write_error
    return JSONResponse({"ok": True, "warnings": warnings})


def _persist_config_and_audit(
    *,
    mgr: StandardManager,
    nmgr: NotificationManager,
    body: dict,
    user_id: int,
    user_id_int: int,
    changed_channels: list[str],
    changed_keys: list[str],
    enabled_changed: bool,
    rules_changed: bool,
    from_ip: str,
    warnings: list[str],
) -> JSONResponse | None:
    """落库 + 审计；返回 None 表示成功，返回 JSONResponse 表示需回给调用方的错误。

    独立成函数的原因有二：① `update_config` 需守住 G-010 的逻辑行上限；
    ② 把"写"集中在一处，使"告警必须先于写"这一安全边界在阅读时一目了然。
    """
    for key, value in body.items():
        if key == "enabled":
            mgr.cfg.set("notification.enabled", bool(value))
            # 同步写入用户偏好表：数据库为权威来源，config.json 兜底
            try:
                mgr.user_service.save_preference(user_id, "notification.enabled", bool(value))
            except Exception as e:
                logger.warning("通知启用状态写入用户偏好表失败: %s", e)
        elif key == "channels":
            # 凭据写入由凭据助手内部完成合并与掩码校验（P2-2：拒绝掩码占位符）
            for ch_name, ch_cfg in value.items():
                if isinstance(ch_cfg, dict) and nmgr._cred_helper:
                    try:
                        nmgr._cred_helper.set_channel(user_id, ch_name, ch_cfg)
                    except ValueError as e:
                        # 掩码占位符被拒绝 → 明确 400，避免前端误判"保存成功"
                        logger.warning(
                            "渠道 %s 配置保存被拒绝: %s", ch_name, e,
                            extra={"source_type": "notification_api", "user_id": user_id},
                        )
                        return JSONResponse({"error": str(e)}, status_code=400)
        elif key == "rules":
            for rule_name, channels in value.items():
                mgr.cfg.set(f"notification.rules.{rule_name}", channels)
    mgr.cfg.save()
    mgr._init_notification()

    # 审计只记字段名与渠道，绝不记凭证值
    if changed_channels or changed_keys or enabled_changed or rules_changed:
        write_audit(
            action="NOTIFICATION_CREDENTIAL_CHANGE",
            resource="PUT /api/notification/config",
            detail={
                "user_id": user_id_int,
                "changed_channels": changed_channels,
                "changed_keys": changed_keys,
                "enabled_changed": enabled_changed,
                "rules_changed": rules_changed,
                "from_ip": from_ip,
                "notify_failed": warnings,
            },
            user_id=user_id_int,
        )
    return None


@router.post("/api/notification/test")
def test_notification(request: Request, body: dict, nmgr=Depends(_get_notification_mgr)):
    """发送测试通知到指定渠道。

    body:
      channel: str     — 渠道名: wechat / telegram / feishu / dingtalk
      title: str       — 标题（可选）
      body: str        — 正文（可选）
      params: dict     — 渠道参数覆盖（可选，如临时测试其他 webhook）
    """
    channel = body.get("channel", "")
    if channel not in ("wechat", "telegram", "feishu", "dingtalk"):
        return {"ok": False, "error": t("notification.api.unsupported_channel").format(ch=channel)}

    msg = NotificationMessage(
        title=body.get("title") or t("notification.api.test_title"),
        body=body.get("body") or t("notification.api.test_body"),
        level="info",
        event_type="test",
    )
    # 渠道参数覆盖（如测试前端的临时_）
    params = body.get("params") or {}
    result = nmgr.test_send(channel, msg, params)
    return result


@router.get("/api/notification/logs")
def get_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: str | None = Query(None),
    status: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    is_read: bool | None = Query(None),
    nmgr=Depends(_get_notification_mgr),
):
    """查询通知发送日志（分页+筛选）。"""
    result = nmgr.ops.get_logs(
        page=page,
        size=page_size,
        channel=channel,
        status=status,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
    )
    return {
        "total": result["total"],
        "page": result["page"],
        "page_size": result["size"],
        "items": [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "channel": r["channel"],
                "title": r["title"],
                "body": r["body"],
                "standard_number": r["standard_number"],
                "status": r["status"],
                "error_msg": r["error_msg"],
                "sent_at": r["sent_at"],
                "is_read": r.get("is_read", 0),
            }
            for r in result["items"]
        ],
    }


@router.post("/api/notification/read")
def mark_notification_read(request: MarkReadRequest, nmgr=Depends(_get_notification_mgr)):
    """标记单条或全部通知为已读。id=None 表示全部标记已读。"""
    try:
        ids = [request.id] if request.id is not None else None
        if request.id is not None:
            # 验证存在
            result = nmgr.ops.get_logs(page=1, size=1, start_date=None, end_date=None)
            existing_ids = {r["id"] for r in result["items"]}
            if request.id not in existing_ids:
                return JSONResponse({"error": f"通知 ID {request.id} 不存在"}, status_code=404)
        count = nmgr.ops.mark_logs_read(ids)
        return {"ok": True, "count": count, "message": "已标记为已读"}
    except Exception as e:
        logger.exception("标记已读失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/notification/unread-count")
def get_unread_count(request: Request, nmgr=Depends(_get_notification_mgr)):
    """获取未读通知数量。"""
    try:
        count = nmgr.ops.get_unread_count()
        return {"count": count}
    except Exception as e:
        logger.exception("获取未读数量失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/notification/logs")
def delete_notification_logs(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    nmgr=Depends(_get_notification_mgr),
):
    """清理通知日志（仅管理员）。删除 days 天前的记录。"""
    try:
        deleted = nmgr.ops.cleanup_logs(days)
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.exception("清理通知日志失败")
        return JSONResponse({"error": str(e)}, status_code=500)


# ──通知策略接口──


class PolicyUpdateRequest(BaseModel):
    """通知策略更新请求体：渠道名、启用状态和订阅事件列表。"""

    channel: str
    enabled: bool | None = None
    events: list[str] | None = None


@router.get("/api/notification/policy")
def get_policy(request: Request, nmgr=Depends(_get_notification_mgr), user_id: int = Depends(_get_user_id)):
    """获取通知策略配置（渠道事件订阅，按用户隔离）。"""
    try:
        policies = nmgr.get_policies(user_id)
        return {"policies": policies}
    except Exception as e:
        logger.exception("获取通知策略失败")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/api/notification/policy")
def put_policy(
    request: Request,
    data: PolicyUpdateRequest,
    nmgr=Depends(_get_notification_mgr),
    user_id: int = Depends(_get_user_id),
):
    """更新通知策略（仅管理员，按用户隔离）。"""
    try:
        nmgr.save_policy(user_id, data.channel, data.enabled, data.events)
        return {"ok": True}
    except Exception as e:
        logger.exception("保存通知策略失败")
        return JSONResponse({"error": str(e)}, status_code=500)
