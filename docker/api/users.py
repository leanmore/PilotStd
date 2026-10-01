# 容器//脚本—用户管理接口
# 权限：用户管理接口需 admin 角色（@require_role）；改密为自助操作，仅需登录认证（裁决 D-3）
import logging

from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd import SUPERUSER_USERNAME
from pilotstd.core.audit import write_audit
from pilotstd.core.notification.security_notifier import client_ip, notify_security_event
from pilotstd.i18n import t

from ..auth import get_current_user_id, require_role
from ..manager import get_manager_dep
from ..users import (
    _validate_password,
    add_user,
    change_password,
    delete_user,
    get_user_by_id,
    list_users,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])


class AddUserRequest(BaseModel):
    """添加用户请求体：用户名、密码和角色（默认 user）。"""

    username: str
    password: str
    role: str = "user"


# 修改密码请求体（独立于，避免权限混淆）
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.get("/api/users")
@require_role("admin")
def api_list_users(request: Request):
    """列出所有用户（仅管理员）。"""
    return {"users": list_users()}


@router.post("/api/users")
@require_role("admin")
def api_add_user(request: Request, body: AddUserRequest):
    """添加用户（仅管理员）。"""
    if not body.username or not body.password:
        raise HTTPException(400, "用户名和密码不能为空")
    if len(body.username) < 2:
        raise HTTPException(400, "用户名至少2个字符")
    if len(body.password) < 8:
        raise HTTPException(400, "密码长度不能少于 8 位")
    try:
        if not add_user(body.username, body.password, body.role):
            raise HTTPException(409, "用户名已存在")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.delete("/api/users/{user_id}")
@require_role("admin")
def api_delete_user(request: Request, user_id: int, mgr=Depends(get_manager_dep)):
    """删除用户（仅管理员，admin 用户不可删除）。"""
    user = mgr.user_service.get_user_by_id(user_id)
    if user and user["username"] == SUPERUSER_USERNAME:
        raise HTTPException(403, "admin 用户不可删除")
    if not delete_user(user_id):
        raise HTTPException(400, "无法删除（不存在或是最后的管理员）")
    return {"ok": True}


@router.put("/api/users/password")
def api_change_password(request: Request, body: ChangePasswordRequest, mgr=Depends(get_manager_dep)):
    """修改当前登录用户的密码（自助操作，仅需登录认证）。

    裁决 D-3（2026-09-26）：原实现带 `@require_role("admin")`，而语义是"改**自己**的
    密码"——普通用户因此永远无法更换自己的弱密码，反而降低安全性，故移除。
    用户隔离由 `get_current_user_id(request)` 保证：只能改自己的。

    顺序与凭证变更相反：**先落库、后告警**。本端点改的是登录密码，与通知渠道凭证
    无关，不存在"告警流向新地址"的问题；反之若先告警后落库，写入失败会产生误报。

    已知限制（裁决 D-2）：改密后既有会话不失效——`SessionStore` 无按用户移除能力，
    本批不碰该模块。此限制在审计 detail 与告警文案中均显式标注为 `sessions_revoked=False`。
    """
    user_id = get_current_user_id(request)
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(400, "用户不存在")
    username = user["username"]
    from_ip = client_ip(request)

    # 前置校验改用与 change_password 同一套规则（users._validate_password），
    # 消除原实现"端点判 ≥4 位、底层判 ≥8 位+字母+数字"的口径分裂——
    # 该分裂会让边界内的密码落到 _validate_password 抛 ValueError，未经捕获即 500。
    if not body.new_password:
        _audit_password_change(username, from_ip, user_id, ok=False, reason="empty_password")
        raise HTTPException(400, "新密码不能为空")
    policy_error = _validate_password(body.new_password)
    if policy_error:
        _audit_password_change(username, from_ip, user_id, ok=False, reason="weak_password")
        raise HTTPException(400, policy_error)

    try:
        ok = change_password(username, body.old_password, body.new_password)
    except ValueError as e:
        # 双保险：底层规则未来若再收紧，也不得退化为 500
        _audit_password_change(username, from_ip, user_id, ok=False, reason="weak_password")
        raise HTTPException(400, str(e)) from e

    if not ok:
        _audit_password_change(username, from_ip, user_id, ok=False, reason="bad_old_password")
        raise HTTPException(400, "旧密码不正确")

    _audit_password_change(
        username,
        from_ip,
        user_id,
        ok=True,
        reason="",
        sessions_revoked=False,  # 已知限制：见函数文档
    )

    # 先落库 → 后告警；告警失败只进 warnings，绝不回滚密码写入
    warnings: list[str] = []
    try:
        notification_mgr = mgr.notification_mgr
        sent, failed = notify_security_event(
            notification_mgr,
            getattr(notification_mgr, "_cred_helper", None),
            user_id,
            "security_password_changed",
            {
                "user_id": str(user_id),
                "from_ip": from_ip,
                "sessions_revoked": False,
            },
        )
        if failed:
            warnings.append(t("notification.api.security_notify_failed").format(channels=", ".join(failed)))
        elif not sent:
            warnings.append(t("notification.api.security_notify_no_channel"))
    except Exception as e:  # noqa: BLE001 - 告警绝不阻断改密
        logger.warning("密码变更告警发送失败: %s", e)
        warnings.append(t("notification.api.security_notify_error"))
    return {"ok": True, "sessions_revoked": False, "warnings": warnings}


def _audit_password_change(
    username: str,
    from_ip: str,
    user_id: int,
    *,
    ok: bool,
    reason: str,
    sessions_revoked: bool = False,
) -> None:
    """写密码变更审计（成功与失败分别记录，失败尝试是暴力破解的可观测信号）。

    detail 只含用户名/来源/原因/会话状态，**绝不记录任何密码或哈希**。
    """
    detail: dict[str, object] = {"username": username, "from_ip": from_ip}
    if ok:
        detail["sessions_revoked"] = sessions_revoked
        if not sessions_revoked:
            detail["known_limitation"] = "existing_sessions_not_revoked"
    else:
        detail["reason"] = reason
    write_audit(
        action="PASSWORD_CHANGE" if ok else "PASSWORD_CHANGE_FAILED",
        resource="PUT /api/users/password",
        detail=detail,
        user_id=user_id,
    )
