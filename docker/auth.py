# 鉴权模块（多用户 + 速率限制 + 跨站伪造防护 + 会话安全标记 + 接口密钥）
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from jose import JWTError, jwt

from pilotstd import ADMIN_ROLE
from pilotstd.core.audit import write_audit

# ── 再导出：状态/常量/中间件迁至 auth_state / auth_middleware，保持既有 import 路径可用 ──
from .auth_middleware import AuthMiddleware as AuthMiddleware
from .auth_middleware import _start_session_cleanup as _start_session_cleanup
from .auth_state import API_RATE_LIMIT as API_RATE_LIMIT
from .auth_state import API_RATE_WINDOW as API_RATE_WINDOW
from .auth_state import API_TOKEN_HEADER as API_TOKEN_HEADER
from .auth_state import AUTH_WHITELIST as AUTH_WHITELIST
from .auth_state import COOKIE_NAME as COOKIE_NAME
from .auth_state import CSRF_HEADER as CSRF_HEADER
from .auth_state import SECRET as SECRET
from .auth_state import TOKEN_EXPIRE_HOURS as TOKEN_EXPIRE_HOURS
from .auth_state import verify_api_key as verify_api_key
from .session_store import get_session_store
from .users import (
    _resolve_audit_identity,
    check_must_change_password,
    clear_login_failures,
    count_recent_failures,
    get_user_by_id,
    get_user_by_username,
    get_user_role,
    init_login_attempts_table,
    init_users_table,
    record_login_failure,
    verify_user,
)

# 登录表一次性初始化标志（login() 用；属登录流程状态，不随后端常量外移）
_init_done = False

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

def get_current_user_id(request: Request) -> int:
    """从请求 Cookie 中解码 JWT，返回当前用户的 user_id（int）。

    ⚠️ 重要：返回值是 user_id（如 1），**不是** username（如 "admin"）。
    调用方如需查询用户记录，应使用 get_user_by_id(user_id)，
    禁止将返回值传给任何形参名为 username 或按 username 查询的函数。
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "未登录")
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "认证失败")
    if get_session_store().get(token) is None:
        raise HTTPException(401, "会话已过期，请重新登录")
    user_id = int(payload["sub"])
    # 类型守卫：防止 JWT sub 字段被意外篡改为非数字值
    if not isinstance(user_id, int):
        logger.error("user_id 类型异常: 期望 int, 实际 %s = %r", type(user_id).__name__, user_id)
        raise HTTPException(500, "Internal error: user_id type mismatch")
    return user_id


def require_role(role: str):
    """装饰器：要求当前用户具有指定角色。

    v3.0 权限控制标准入口。拒绝时写 ACCESS_DENIED 审计日志。
    支持 FastAPI 路由函数和普通 Service 方法。

    Usage:
        @router.put("/api/settings")
        @require_role("admin")
        def put_settings(...): ...
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 从参数中提取对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                for v in kwargs.values():
                    if isinstance(v, Request):
                        request = v
                        break

            # 从令牌获取当前角色与主体
            # ⚠️ v3.0 起 JWT 的 `sub` 是 **user_id**（`_generate_token` 写 `str(user_id)`），
            # 不是 username——故变量名为 subject 而非 username（L-04 修复）。
            current_role = "user"
            subject = "unknown"
            if request is not None:
                token = request.cookies.get(COOKIE_NAME)
                if token:
                    try:
                        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
                        current_role = payload.get("role", "user")
                        subject = payload.get("sub", "unknown")
                    except JWTError:
                        pass

            if current_role != ADMIN_ROLE and current_role != role:
                # L-04：审计需可读的 username，但 `sub` 是 user_id → 在拒绝路径上反查。
                audit_user_id, audit_username = _resolve_audit_identity(subject)
                write_audit(
                    action="ACCESS_DENIED",
                    resource=f"{request.method} {request.url.path}" if request else func.__name__,
                    detail={
                        "required_role": role,
                        "actual_role": current_role,
                        "username": audit_username,
                    },
                    # 显式传 user_id，使审计列与 detail 一致（不再依赖 ContextVar 是否存在）
                    user_id=audit_user_id,
                )
                raise HTTPException(403, "权限不足")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# 白名单：(路径前缀,{允许的网络方法})，方法集合为空表示允许所有方法

# 登录失败计数（持久化到数据库查询），仅保留5分钟内的记录
MAX_ATTEMPTS = 100  # 5 分钟内最多 100 次失败（压测放宽）
LOCKOUT_SECONDS = 300  # 锁定 5 分钟

# 登录失败安全告警阈值（第 8 批）：与上面的限流阈值**故意解耦**。
# MAX_ATTEMPTS=100 是为压测放宽的限流闸门，作为告警阈值过高（几乎不会触发）；
# 本阈值取"已构成暴力破解嫌疑"的量级。告警按 IP 在窗口内累计，且只在**恰好**
# 达到阈值时发一次（继续失败不刷屏），登录成功清空计数后再次累积可再次触发。
LOGIN_FAILURE_ALERT_THRESHOLD = 5


# 锁定拒绝（429）的审计留痕去重：IP -> 上次留痕时刻（墙钟 time.time()）。
# 与 _api_rate_limit 同模式（进程内 dict + 锁 + 按访问修剪）。
_lockout_audited_at: dict[str, float] = {}
_lockout_audit_lock = threading.Lock()


def _audit_lockout_once(client_ip_addr: str, failures: int, now: float) -> None:
    """锁定（429）的审计留痕：同一 IP 每 LOCKOUT_SECONDS 只写一次。

    **为何不用 `count == MAX_ATTEMPTS` 精确判断**：本函数在 login() 的计数检查处调用，
    而该路径**不写 login_attempts**（record_login_failure 在密码验证失败分支，位于该
    检查**之后**）→ 攻击者持续请求时计数**停滞在 ≥MAX_ATTEMPTS 不再增长** → 等值判断
    每次请求都命中 → 刷屏。故必须用时间闸门。（对照：告警侧 :308 在 record_login_failure
    之后调用，计数每次 +1，故可用"恰好等于阈值"判断。）

    **时间源**：`now` 由调用方传入 login() 计算的 `time.time()`，与该函数的 `cutoff`
    **同源**（本项目统一使用墙钟；不用 monotonic——会与 count_recent_failures 的墙钟
    窗口形成双时钟，在系统时间跳变时错位）。

    **锁范围**：读取 + 判定 + 清理 + 更新，均在锁内完成（镜像 _check_rate_limit）。
    `write_audit` 的 DB I/O 在**锁外**，避免慢 DB 阻塞并发登录。

    **失败语义**：write_audit 静默失败（见 pilotstd/core/audit.py）时 dict 已更新 →
    该窗口不再重试。这是有意设计——审计是"尽力留痕"，与 write_audit 的不阻断契约一致；
    失败经 logger.warning(exc_info=True) 运维可见。
    """
    with _lockout_audit_lock:
        last = _lockout_audited_at.get(client_ip_addr)
        if last is not None and now - last < LOCKOUT_SECONDS:
            return  # 同窗口内已留痕，不再重复
        # 惰性清理：镜像 _check_rate_limit 的按访问修剪（保留 2 倍窗口，容忍时钟抖动）
        stale = [ip for ip, ts in _lockout_audited_at.items() if now - ts > LOCKOUT_SECONDS * 2]
        for ip in stale:
            del _lockout_audited_at[ip]
        _lockout_audited_at[client_ip_addr] = now
    # 函数内 import：与 _notify_login_failure（本文件）对 write_audit 的既有处理一致；
    # 已核实无循环导入风险（pilotstd/core/audit.py 仅导入 pilotstd.core.*）。
    from pilotstd.core.audit import write_audit

    write_audit(
        action="LOGIN_ATTEMPT_BLOCKED",
        resource="POST /api/login",
        detail={"from_ip": client_ip_addr, "failures": failures, "window_seconds": LOCKOUT_SECONDS},
        user_id=None,
    )


def _notify_login_failure(request: Request, client_ip: str, username: str) -> None:
    """登录失败达到阈值时写审计 + 发安全告警（第 8 批）。

    设计要点：
    - **按 IP 累计**（`count_recent_failures` 的口径）且只在**恰好**达到阈值时触发一次；
      登录成功会 `clear_login_failures`，故清空后再次累积可再次告警。
    - 登录接口是**未认证**路径，`write_audit` 的 ContextVar 尚未注入，故显式传
      `user_id=None`（audit_logs 允许 NULL，见 v45 迁移）。
    - **不记录密码**；用户名也不记入 detail——登录失败响应本身不区分"用户不存在"
      与"密码错误"（防用户名枚举），审计与告警同样遵循该口径。
    - 任何异常都不得影响登录响应（401 必须照常返回）。
    """
    try:
        from .users import count_recent_failures

        failures = count_recent_failures(client_ip, time.time() - LOCKOUT_SECONDS)
        if failures < LOGIN_FAILURE_ALERT_THRESHOLD:
            return
        if failures > LOGIN_FAILURE_ALERT_THRESHOLD:
            return  # 阈值后继续失败不重复告警（仅在恰好达到时发一次）
        from pilotstd.core.audit import write_audit

        write_audit(
            action="LOGIN_FAILED",
            resource="POST /api/login",
            detail={"from_ip": client_ip, "failures": failures, "window_seconds": LOCKOUT_SECONDS},
            user_id=None,
        )
        from .manager import get_manager

        mgr = get_manager()
        notification_mgr = getattr(mgr, "notification_mgr", None)
        if notification_mgr is None:
            return
        notification_mgr.send_event(
            "security_login_failed",
            {
                "from_ip": client_ip,
                "failures": failures,
                "window_seconds": LOCKOUT_SECONDS,
                "username": username,
            },
        )
    except Exception:
        # 告警/审计失败绝不能改变登录失败的响应语义
        logger.warning("登录失败告警发送失败", exc_info=True)


def _generate_token(user_id: int = 1, role: str = "user") -> str:
    """生成 JWT token — v3.0: sub=str(user_id)，载荷精简。

    旧格式 {sub: username} 仍兼容（dispatch 中 digit 判断走 users 表查询回退）。
    """
    now = datetime.now(timezone.utc)
    return jwt.encode(  # type: ignore[no-any-return]
        {
            "sub": str(user_id),
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),
        },
        SECRET,
        algorithm="HS256",
    )


def _is_https(request: Request) -> bool:
    """判断当前请求是否通过 HTTPS（支持反向代理）。"""
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("X-Forwarded-Proto", "")
    return cast(bool, forwarded == "https")


@router.post("/api/login")
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(...),
):
    """用户登录，含速率限制。用户名需在 Web UI 中手动输入。"""
    global _init_done
    if not _init_done:
        init_users_table()
        init_login_attempts_table()
        _init_done = True

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - LOCKOUT_SECONDS

    # 超限检查（持久化到数据库查询，进程重启后仍有效）
    # failures 单次查询后复用：两次调用既重复 DB 查询，又可能因并发导致
    # "审计记录的 failures 与触发判定的值不一致"（极端情况低于阈值）。
    failures = count_recent_failures(client_ip, cutoff)
    if failures >= MAX_ATTEMPTS:
        _audit_lockout_once(client_ip, failures=failures, now=now)
        raise HTTPException(429, "请求过于频繁，请稍后重试")

    if not verify_user(username, password):
        record_login_failure(client_ip)
        _notify_login_failure(request, client_ip, username)
        raise HTTPException(401, "认证失败")

    # 登录成功，清除失败记录
    clear_login_failures(client_ip)

    must_change = check_must_change_password(username)
    role = get_user_role(username)
    user_row = get_user_by_username(username)
    user_id = user_row["id"] if user_row else 1
    token = _generate_token(user_id=user_id, role=role)
    get_session_store().add(token, user_id, username, ttl_seconds=TOKEN_EXPIRE_HOURS * 3600)
    csrf_token = secrets.token_hex(32)  # 独立 CSRF token，不复用 JWT
    resp = JSONResponse({"ok": True, "username": username, "role": role, "must_change_password": must_change})
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=_is_https(request),
        samesite="strict",
        path="/",
    )
    resp.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=False,  # 前端需读取此 cookie 值写入 X-CSRF-Token 请求头
        secure=_is_https(request),
        samesite="strict",
        path="/",
    )
    return resp


@router.get("/api/auth/me")
def auth_me(request: Request):
    """返回当前登录用户的身份信息（用户名 + 角色），供前端权限渲染用。

    get_current_user_id() 返回 JWT sub (user_id)，需通过 id 查 users 表获取
    实际 username 和 role，而非直接传给 get_user_role()（该函数期望 username）。
    """
    user_id = get_current_user_id(request)

    if user_id:
        try:
            from pilotstd.core.config import get_db_path
            from pilotstd.core.db import Database

            db = Database(get_db_path())
            row = db.fetchone(
                "SELECT id, username, role FROM users WHERE id = ?",
                (user_id,),
            )
            if row:
                return {"id": row["id"], "username": row["username"], "role": row["role"]}
        except Exception:
            pass

    # 降级兜底：兼容旧版令牌(=)或数据库查询失败场景
    fallback_id = get_current_user_id(request)
    fallback_user = get_user_by_id(fallback_id) if fallback_id else None
    role = get_user_role(fallback_user["username"]) if fallback_user else ""
    return {"username": fallback_user["username"] if fallback_user else "", "role": role or ""}


@router.post("/api/logout")
def logout(request: Request):
    """用户登出：从会话存储中移除 token，清除客户端 Cookie。"""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        get_session_store().remove(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME, path="/")
    resp.delete_cookie("csrf_token", path="/")
    return resp


