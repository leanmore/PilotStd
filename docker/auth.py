# 鉴权模块（多用户 + 速率限制 + 跨站伪造防护 + 会话安全标记 + 接口密钥）
import hashlib
import logging
import os
import secrets
import threading
import time
import warnings
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from fastapi import Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from pilotstd import ADMIN_ROLE

from ._static_token import _ensure_static_token_in_db
from .session_store import get_session_store
from .users import (
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

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(32)

# 应用启动时确保用户表存在
_init_done = False

TOKEN_EXPIRE_HOURS = 2  # jwt 过期时间（小时），可通过 TOKEN_EXPIRE_HOURS 环境变量覆盖
COOKIE_NAME = "pilotstd_token"
CSRF_HEADER = "X-CSRF-Token"
API_TOKEN_HEADER = "X-API-KEY"  # 静态令牌 Header（参考 MoviePilot）



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


def get_current_username(request: Request) -> int:
    """⚠️ DEPRECATED: 实际返回 user_id 而非 username，函数名具有误导性。

    请使用 get_current_user_id() 获取用户 ID。
    将在后续版本移除。
    """
    warnings.warn(
        "get_current_username() is deprecated — returns user_id, not username. Use get_current_user_id() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_current_user_id(request)


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

    from pilotstd.core.audit import write_audit

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

            # 从令牌获取当前角色
            current_role = "user"
            username = "unknown"
            if request is not None:
                token = request.cookies.get(COOKIE_NAME)
                if token:
                    try:
                        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
                        current_role = payload.get("role", "user")
                        username = payload.get("sub", "unknown")
                    except JWTError:
                        pass

            if current_role != ADMIN_ROLE and current_role != role:
                write_audit(
                    action="ACCESS_DENIED",
                    resource=f"{request.method} {request.url.path}" if request else func.__name__,
                    detail={"required_role": role, "actual_role": current_role, "username": username},
                )
                raise HTTPException(403, "权限不足")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# 白名单：(路径前缀,{允许的网络方法})，方法集合为空表示允许所有方法
AUTH_WHITELIST: list[tuple[str, set[str]]] = [
    ("/api/login", set()),
    ("/api/logout", set()),
    ("/api/health", set()),
    ("/api/system/version", {"GET"}),
    ("/api/logs", {"GET"}),
    # 登录页背景图 URL（公开接口）：仅暴露 appearance.login_bg 单字段，替代
    # 仅管理员的 GET /api/settings 在未登录态下的 401 拦截问题
    ("/api/login-background", set()),
    ("/api/backgrounds", set()),
    ("/assets", set()),
]

# 登录失败计数（持久化到数据库查询），仅保留5分钟内的记录
MAX_ATTEMPTS = 100  # 5 分钟内最多 100 次失败（压测放宽）
LOCKOUT_SECONDS = 300  # 锁定 5 分钟

# 接口全局速率限制：{:[,...]}，=用户名或
_api_rate_limit: dict[str, list[float]] = defaultdict(list)
_api_rate_lock = threading.Lock()  # 保护 _api_rate_limit 并发读写
API_RATE_LIMIT = 1000  # 每分钟最多 1000 次请求（压测放宽）
API_RATE_WINDOW = 60  # 窗口 60 秒


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
    if count_recent_failures(client_ip, cutoff) >= MAX_ATTEMPTS:
        raise HTTPException(429, "请求过于频繁，请稍后重试")

    if not verify_user(username, password):
        record_login_failure(client_ip)
        raise HTTPException(401, "认证失败")

    # 登录成功，清除失败记录
    clear_login_failures(client_ip)

    must_change = check_must_change_password(username)
    role = get_user_role(username)
    user_row = get_user_by_username(username)
    user_id = user_row["id"] if user_row else 1
    token = _generate_token(user_id=user_id, role=role)
    get_session_store().add(token, {"username": username}, ttl_seconds=TOKEN_EXPIRE_HOURS * 3600)
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


def verify_api_key(token: str) -> dict | None:
    """验证 API Key。返回 {key_id, scopes} 或 None。
    token 以 "pst_" 开头，提取后 SHA256 哈希查表，验证 is_active=1。
    """
    if not token.startswith("pst_"):
        return None
    actual_token = token[4:]  # 去掉 "pst_" 前缀后做 SHA256 哈希
    key_hash = hashlib.sha256(actual_token.encode()).hexdigest()
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    db = Database(get_db_path())
    row = db.fetchone(
        "SELECT key_id, scopes FROM api_keys WHERE key_hash = ? AND is_active = 1",
        (key_hash,),
    )
    if row is None:
        return None
    # 更新__
    db.execute(
        "UPDATE api_keys SET last_used_at = datetime('now', 'localtime') WHERE key_hash = ?",
        (key_hash,),
    )
    try:
        import json

        scopes = json.loads(row["scopes"]) if row["scopes"] else []
    except (json.JSONDecodeError, TypeError):
        scopes = []
    return {"key_id": row["key_id"], "scopes": scopes}


class AuthMiddleware(BaseHTTPMiddleware):
    """鉴权中间件：白名单放行 + Origin/Referer 校验 + Cookie JWT 校验 + API Key 校验 + CSRF 检查。"""

    async def _check_public_path(self, request, path: str) -> bool:
        """白名单路径 + 非 API 路径放行。返回 True 表示已放行（无需鉴权）。"""
        for w_path, w_methods in AUTH_WHITELIST:
            if path.startswith(w_path) and (not w_methods or request.method in w_methods):
                return True
        if not path.startswith("/api/"):
            return True
        return False

    def _check_rate_limit(self, request) -> JSONResponse | None:
        """全局 API 速率限制。返回 429 响应或 None（通过）。"""
        now = time.time()
        client_ip = request.client.host if request.client else "unknown"
        cutoff = now - API_RATE_WINDOW
        with _api_rate_lock:
            _api_rate_limit[client_ip] = [t for t in _api_rate_limit[client_ip] if t > cutoff]
            if not _api_rate_limit[client_ip]:
                del _api_rate_limit[client_ip]
            elif len(_api_rate_limit[client_ip]) >= API_RATE_LIMIT:
                return JSONResponse({"error": "请求过于频繁，请稍后重试"}, 429)
            _api_rate_limit[client_ip].append(now)
        return None

    def _authenticate_api_key(self, request) -> bool:
        """三通道 API Key 校验：Authorization Bearer / X-API-KEY Header / ?token 查询参数。
        返回 True 表示已认证。失败时返回 False 或直接返回 401（pst_ 前缀 token 不回落 JWT）。"""
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get(API_TOKEN_HEADER, "")
        query_token = request.query_params.get("token", "")

        api_token = ""
        if auth_header.startswith("Bearer "):
            api_token = auth_header[7:]
        elif api_key_header:
            api_token = api_key_header
        elif query_token:
            api_token = query_token

        if not api_token:
            return False

        key_info = verify_api_key(api_token)
        if key_info:
            request.state.api_key_id = key_info["key_id"]
            request.state.api_key_scopes = key_info["scopes"]
            return True
        # _前缀验证失败直接401（不回落令牌）
        if api_token.startswith("pst_"):
            raise HTTPException(401, "认证失败")
        return False

    def _authenticate_session(self, request) -> dict:
        """Origin/Referer 跨源校验 + Cookie JWT 校验 + CSRF 检查。

        失败直接抛 HTTPException。成功返回解码后的 JWT payload (dict)。
        """
        origin = request.headers.get("Origin", "") or request.headers.get("Referer", "")
        if origin:
            from urllib.parse import urlparse

            try:
                origin_host = urlparse(origin).hostname
                request_host = request.headers.get("Host", "").split(":")[0]
                if origin_host and request_host and origin_host != request_host:
                    raise HTTPException(403, "认证失败")
            except Exception:
                raise HTTPException(403, "认证失败")

        token = request.cookies.get(COOKIE_NAME)
        if not token:
            raise HTTPException(401, "认证失败")
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        except JWTError:
            raise HTTPException(401, "认证失败")

        if get_session_store().get(token) is None:
            raise HTTPException(401, "会话已过期，请重新登录")

        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            csrf_header = request.headers.get(CSRF_HEADER, "")
            csrf_cookie = request.cookies.get("csrf_token", "")
            if not csrf_header or csrf_header != csrf_cookie:
                raise HTTPException(403, "认证失败")

        return cast("dict[Any, Any]", payload)

    async def dispatch(self, request, call_next):
        path = request.url.path

        _ensure_static_token_in_db()

        # 白名单+非接口路径放行
        if await self._check_public_path(request, path):
            return await call_next(request)

        # 全局速率限制
        rate_limit_resp = self._check_rate_limit(request)
        if rate_limit_resp:
            return rate_limit_resp

        # 接口校验
        try:
            if self._authenticate_api_key(request):
                return await call_next(request)
        except HTTPException:
            return JSONResponse({"error": "认证失败"}, 401)

        # 令牌+跨站伪造防护校验→注入
        try:
            payload = self._authenticate_session(request)
        except HTTPException as e:
            return JSONResponse({"error": "认证失败"}, e.status_code)

        # 版本三0:注入_到请求上下文（/防止异步泄漏）
        from pilotstd.core.config import get_db_path
        from pilotstd.core.context import _current_user_id, set_current_user_id
        from pilotstd.core.db import Database

        user_id = None
        sub = payload.get("sub", "")
        if sub.isdigit():
            user_id = int(sub)
        else:
            db = Database(get_db_path())
            row = db.fetchone("SELECT id FROM users WHERE username = ?", (sub,))
            if row:
                user_id = row["id"]

        if user_id is not None:
            token_ctx = set_current_user_id(user_id)
            try:
                return await call_next(request)
            finally:
                _current_user_id.reset(token_ctx)

        return await call_next(request)


# ──会话清理后台线程（每小时清理过期）────────────────────

_cleanup_started = False
_cleanup_lock = threading.Lock()


def _start_session_cleanup() -> None:
    """启动后台线程定期清理过期会话。幂等——多次调用只启动一次。"""
    global _cleanup_started
    if _cleanup_started:
        return
    with _cleanup_lock:
        if _cleanup_started:
            return
        _cleanup_started = True

    def _cleanup_loop() -> None:
        """后台会话清理循环：每小时调用一次 cleanup_expired()，移除过期 token。"""
        while True:
            time.sleep(3600)
            try:
                store = get_session_store()
                removed = store.cleanup_expired()
                if removed > 0:
                    import logging

                    logging.getLogger("pilotstd.auth").debug("会话清理: 移除 %d 条过期", removed)
            except Exception:
                pass

    t = threading.Thread(target=_cleanup_loop, daemon=True, name="session-cleanup")
    t.start()
