# 容器//_脚本—版本三0:用户注册端点（从脚本拆分，控制文件行数）
import json
import os
import secrets
import time

from fastapi import Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.audit import write_audit
from pilotstd.core.notification.security_notifier import client_ip

from ..auth import (
    COOKIE_NAME,
    TOKEN_EXPIRE_HOURS,
    _generate_token,
    _is_https,
    get_session_store,
)
from ..users import add_user, get_user_by_username, get_user_role, init_users_table

router = APIRouter(tags=["auth"])

_ENABLE_REGISTRATION = os.environ.get("ENABLE_REGISTRATION", "false").lower() == "true"
_registration_attempts: dict[str, list[float]] = {}
REGISTER_MAX_ATTEMPTS = 5
REGISTER_WINDOW = 3600


def _audit_registration(
    request: Request, *, ok: bool, username: str, reason: str = "", actor_id: int | None = None
) -> None:
    """写自助注册审计（成功与失败分别记录）。

    注册是**未认证**路径，`write_audit` 的 ContextVar 未注入，故显式传 user_id
    （成功时为新建用户 id，失败时为 None）。detail **不记密码**。
    自助注册是"注册误开"的唯一可观测信号，故失败分支（功能关闭/限流/校验失败）同样留痕。
    """
    detail: dict[str, object] = {"from_ip": client_ip(request)}
    if username:
        detail["username"] = username
    if ok:
        detail["result"] = "ok"
    else:
        detail["reason"] = reason
    write_audit(
        action="USER_REGISTER" if ok else "USER_REGISTER_FAILED",
        resource="POST /api/auth/register",
        detail=detail,
        user_id=actor_id,
    )


@router.post("/api/auth/register")
def register(request: Request, username: str = Form(""), password: str = Form(...)):
    """用户自助注册 — ENABLE_REGISTRATION=true 时开放。

    注册成功后自动登录：创建用户 → 初始化偏好 → 返回 JWT cookie。
    IP 限流: REGISTER_MAX_ATTEMPTS 次 / REGISTER_WINDOW 秒。

    全部出口（1 成功 + 6 失败）均写审计——L2 接线约定：注册是"注册误开"的
    唯一可观测信号，失败尝试（开关关闭/限流/校验失败）与成功同样需要留痕。
    """
    # 功能开关检查
    if not _ENABLE_REGISTRATION:
        _audit_registration(request, ok=False, username=username, reason="registration_disabled")
        raise HTTPException(403, "注册功能未开放")

    # 限流：滑动窗口计数
    # 注：局部变量名避开模块级导入的 client_ip()（审计封装需要该函数，同名会被局部遮蔽）
    client_addr = request.client.host if request.client else "unknown"
    now_ts = time.time()
    cutoff = now_ts - REGISTER_WINDOW
    attempts = [t for t in _registration_attempts.get(client_addr, []) if t > cutoff]
    if len(attempts) >= REGISTER_MAX_ATTEMPTS:
        _audit_registration(request, ok=False, username=username, reason="rate_limited")
        raise HTTPException(429, "注册请求过于频繁，请稍后重试")
    attempts.append(now_ts)
    _registration_attempts[client_addr] = attempts

    # 输入校验
    if not username or len(username) < 2:
        _audit_registration(request, ok=False, username=username, reason="username_too_short")
        raise HTTPException(400, "用户名至少2个字符")
    if not password or len(password) < 8:
        _audit_registration(request, ok=False, username=username, reason="password_too_short")
        raise HTTPException(400, "密码长度不能少于 8 位")

    # 确保用户表存在
    init_users_table()

    # 创建用户（）
    try:
        if not add_user(username, password, role="user"):
            _audit_registration(request, ok=False, username=username, reason="username_exists")
            raise HTTPException(409, "用户名已存在")
    except ValueError as e:
        _audit_registration(request, ok=False, username=username, reason="invalid:{}".format(e))
        raise HTTPException(400, str(e))

    # 初始化默认偏好 + 自动登录
    user_row = get_user_by_username(username)
    uid = user_row["id"] if user_row else 1
    _init_default_preferences(uid)
    role = get_user_role(username)
    token = _generate_token(user_id=uid, role=role)
    get_session_store().add(token, uid, username, ttl_seconds=TOKEN_EXPIRE_HOURS * 3600)
    csrf_token = secrets.token_hex(32)
    resp = JSONResponse({"ok": True, "username": username, "role": role, "must_change_password": False})
    # 安全属性：++
    resp.set_cookie(COOKIE_NAME, token, httponly=True, secure=_is_https(request), samesite="strict", path="/")
    resp.set_cookie("csrf_token", csrf_token, httponly=False, secure=_is_https(request), samesite="strict", path="/")
    _audit_registration(request, ok=True, username=username, actor_id=uid)
    return resp


def _init_default_preferences(user_id: int) -> None:
    """为新用户插入默认偏好（幂等 INSERT OR IGNORE）。"""
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    defaults = {"ui.theme": "light", "ui.lang": "zh-CN"}
    db = Database(get_db_path())
    for k, v in defaults.items():
        db.execute(
            "INSERT OR IGNORE INTO user_preferences (user_id, preference_key, preference_value) VALUES (?, ?, ?)",
            (user_id, k, json.dumps(v)),
        )
    db.close()
