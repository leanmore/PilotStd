# docker/auth.py — JWT 鉴权模块（多用户 + 速率限制 + CSRF 保护 + Cookie 安全标记）
import os
import time
import secrets
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import Form, HTTPException, Request
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from .users import init_users_table, verify_user, init_login_attempts_table, \
    record_login_failure, clear_login_failures, count_recent_failures, \
    check_must_change_password

router = APIRouter(tags=["auth"])

SECRET = os.environ.get("JWT_SECRET") or secrets.token_hex(32)

# 应用启动时确保用户表存在
_init_done = False

TOKEN_EXPIRE_HOURS = 2  # jwt 过期时间（小时），可通过 TOKEN_EXPIRE_HOURS 环境变量覆盖
COOKIE_NAME = "pilotstd_token"
CSRF_HEADER = "X-CSRF-Token"


def get_current_username(request: Request) -> str:
    """从请求 Cookie 中解码 JWT，返回当前用户名。"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "未登录")
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return payload.get("sub", "")
    except JWTError:
        raise HTTPException(401, "认证失败")


def require_admin(request: Request) -> str:
    """要求当前用户为 admin 角色，否则返回 405。"""
    username = get_current_username(request)
    from .users import get_user_role
    role = get_user_role(username)
    if role != "admin":
        raise HTTPException(405, "仅管理员可执行此操作")
    return username
# 白名单：(路径前缀, {允许的HTTP方法})，方法集合为空表示允许所有方法
AUTH_WHITELIST: list[tuple[str, set[str]]] = [
    ("/api/login", set()),
    ("/api/logout", set()),
    ("/api/health", set()),
    ("/api/settings", {"GET"}),
    ("/api/system/version", {"GET"}),
    ("/api/logs", {"GET"}),
    ("/api/backgrounds", set()),
    ("/assets", set()),
]

# 登录失败计数（持久化到 SQLite），仅保留 5 分钟内的记录
MAX_ATTEMPTS = 5          # 5 分钟内最多 5 次失败
LOCKOUT_SECONDS = 300     # 锁定 5 分钟

# API 全局速率限制：{key: [timestamp, ...]}，key = 用户名 或 IP
_api_rate_limit: dict[str, list[float]] = defaultdict(list)
_api_rate_lock = threading.Lock()  # 保护 _api_rate_limit 并发读写
API_RATE_LIMIT = 60       # 每分钟最多 60 次请求
API_RATE_WINDOW = 60      # 窗口 60 秒


def _generate_token(username: str = "admin") -> str:
    """生成 JWT token，包含用户名、签发时间、过期时间。"""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": username,
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
    return forwarded == "https"


@router.post("/api/login")
def login(request: Request, username: str = Form(os.environ.get("ADMIN_USERNAME", "admin")), password: str = Form(...)):
    """用户登录，含速率限制。默认用户名可通过 ADMIN_USERNAME 环境变量配置。"""
    global _init_done
    if not _init_done:
        init_users_table()
        init_login_attempts_table()
        _init_done = True

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - LOCKOUT_SECONDS

    # 超限检查（持久化到 SQLite，进程重启后仍有效）
    if count_recent_failures(client_ip, cutoff) >= MAX_ATTEMPTS:
        raise HTTPException(429, "请求过于频繁，请稍后重试")

    if not verify_user(username, password):
        record_login_failure(client_ip)
        raise HTTPException(401, "认证失败")

    # 登录成功，清除失败记录
    clear_login_failures(client_ip)

    token = _generate_token(username)
    csrf_token = secrets.token_hex(32)  # 独立 CSRF token，不复用 JWT
    must_change = check_must_change_password(username)
    resp = JSONResponse({"ok": True, "username": username, "must_change_password": must_change})
    resp.set_cookie(
        COOKIE_NAME, token,
        httponly=True,
        secure=_is_https(request),
        samesite="strict",
        path="/",
    )
    resp.set_cookie(
        "csrf_token", csrf_token,
        httponly=False,  # 前端需读取此 cookie 值写入 X-CSRF-Token 请求头
        secure=_is_https(request),
        samesite="strict",
        path="/",
    )
    return resp


@router.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME, path="/")
    resp.delete_cookie("csrf_token", path="/")
    return resp


class AuthMiddleware(BaseHTTPMiddleware):
    """鉴权中间件：白名单放行 + Origin/Referer 校验 + Cookie token 校验 + CSRF 检查。"""

    async def dispatch(self, request, call_next):
        path = request.url.path

        # 白名单检查：路径+方法匹配则免认证放行；仅路径匹配但方法不匹配时，回落走认证流程
        for w_path, w_methods in AUTH_WHITELIST:
            if path.startswith(w_path) and (not w_methods or request.method in w_methods):
                return await call_next(request)
        # 非 API 路径放行（前端静态文件）
        if not path.startswith("/api/"):
            return await call_next(request)

        # 全局速率限制：按 IP 限流，白名单路径已放行到此的 API 请求
        now = time.time()
        client_ip = request.client.host if request.client else "unknown"
        cutoff = now - API_RATE_WINDOW
        with _api_rate_lock:
            _api_rate_limit[client_ip] = [t for t in _api_rate_limit[client_ip] if t > cutoff]
            if not _api_rate_limit[client_ip]:
                del _api_rate_limit[client_ip]  # 清理过期IP条目，防止字典无限增长
            elif len(_api_rate_limit[client_ip]) >= API_RATE_LIMIT:
                return JSONResponse({"error": "请求过于频繁，请稍后重试"}, 429)
            _api_rate_limit[client_ip].append(now)

        # 跨源检查：有 Origin/Referer 时校验与请求 Host 一致
        origin = request.headers.get("Origin", "") or request.headers.get("Referer", "")
        if origin:
            from urllib.parse import urlparse
            try:
                origin_host = urlparse(origin).hostname
                request_host = request.headers.get("Host", "").split(":")[0]
                if origin_host and request_host and origin_host != request_host:
                    return JSONResponse({"error": "认证失败"}, 403)
            except Exception:
                return JSONResponse({"error": "认证失败"}, 403)

        # Cookie token 校验
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return JSONResponse({"error": "认证失败"}, 401)
        try:
            jwt.decode(token, SECRET, algorithms=["HS256"])
        except JWTError:
            return JSONResponse({"error": "认证失败"}, 401)

        # CSRF 检查：状态变更操作须携带与 csrf_token Cookie 一致的 X-CSRF-Token 请求头
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            csrf_header = request.headers.get(CSRF_HEADER, "")
            csrf_cookie = request.cookies.get("csrf_token", "")
            if not csrf_header or csrf_header != csrf_cookie:
                return JSONResponse({"error": "认证失败"}, 403)

        return await call_next(request)
