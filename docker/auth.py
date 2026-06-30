# docker/auth.py — JWT 鉴权模块（多用户 + 速率限制 + CSRF 保护 + Cookie 安全标记 + API Key）
import hashlib
import os
import secrets
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from pilotstd import SUPERUSER_USERNAME

from .users import (
    check_must_change_password,
    clear_login_failures,
    count_recent_failures,
    init_login_attempts_table,
    init_users_table,
    record_login_failure,
    verify_user,
)

router = APIRouter(tags=["auth"])

SECRET = os.environ.get("JWT_SECRET") or secrets.token_hex(32)

# 应用启动时确保用户表存在
_init_done = False

TOKEN_EXPIRE_HOURS = 2  # jwt 过期时间（小时），可通过 TOKEN_EXPIRE_HOURS 环境变量覆盖
COOKIE_NAME = "pilotstd_token"
CSRF_HEADER = "X-CSRF-Token"
API_TOKEN_HEADER = "X-API-KEY"  # 静态令牌 Header（参考 MoviePilot）

# 静态 API 令牌：从 PILOTSTD_API_TOKEN 环境变量读取，未设置则自动生成
_STATIC_API_TOKEN = os.environ.get("PILOTSTD_API_TOKEN") or secrets.token_hex(32)
_STATIC_TOKEN_INITIALIZED = False


def _ensure_static_token_in_db():
    """确保静态令牌在 api_keys 表中存在且有效（幂等）。

    每次应用启动时调用——若 PILOTSTD_API_TOKEN 已设置且与 DB 中一致则跳过，
    否则创建/更新一条 key_id='pst_static' 的记录。
    """
    global _STATIC_TOKEN_INITIALIZED
    if _STATIC_TOKEN_INITIALIZED:
        return
    try:
        from pilotstd.core.config import get_db_path
        from pilotstd.core.db import Database

        db = Database(get_db_path())
        db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL,
                description TEXT DEFAULT '',
                scopes TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_used_at TEXT
            )
        """)
        key_hash = hashlib.sha256(_STATIC_API_TOKEN.encode()).hexdigest()
        existing = db.fetchone("SELECT key_hash FROM api_keys WHERE key_id = 'pst_static'")
        if existing:
            if existing["key_hash"] != key_hash:
                db.execute(
                    "UPDATE api_keys SET key_hash=?, is_active=1 WHERE key_id='pst_static'",
                    (key_hash,),
                )
        else:
            db.execute(
                "INSERT INTO api_keys (key_id, key_hash, description, scopes, is_active)"
                " VALUES ('pst_static', ?, 'static-token-from-env', '[\"query:read\", \"announce:read\"]', 1)",
                (key_hash,),
            )
        db.close()
        _STATIC_TOKEN_INITIALIZED = True
    except Exception:
        pass  # 首次启动时 DB 可能尚未初始化，后续请求重试


def get_static_token() -> str:
    """返回当前静态令牌值（供 settings API 读取）。"""
    return _STATIC_API_TOKEN


def refresh_static_token() -> str:
    """重新生成静态令牌，更新内存缓存 + 数据库 + 环境变量。

    返回新令牌值。刷新后旧令牌立即失效。
    """
    global _STATIC_API_TOKEN, _STATIC_TOKEN_INITIALIZED
    import hashlib as _hashlib
    import secrets as _secrets

    new_token = _secrets.token_hex(32)
    new_hash = _hashlib.sha256(new_token.encode()).hexdigest()
    _STATIC_API_TOKEN = new_token
    os.environ["PILOTSTD_API_TOKEN"] = new_token
    try:
        from pilotstd.core.config import get_db_path
        from pilotstd.core.db import Database

        db = Database(get_db_path())
        existing = db.fetchone("SELECT key_hash FROM api_keys WHERE key_id = 'pst_static'")
        if existing:
            db.execute(
                "UPDATE api_keys SET key_hash=?, is_active=1 WHERE key_id='pst_static'",
                (new_hash,),
            )
        else:
            db.execute(
                "INSERT INTO api_keys (key_id, key_hash, description, scopes, is_active)"
                " VALUES ('pst_static', ?, 'static-token-from-env',"
                ' \'["query:read", "announce:read"]\', 1)',
                (new_hash,),
            )
        db.close()
    except Exception:
        pass
    # 回写 .env 文件，确保重启后令牌不丢失
    _dotenv_path = os.path.join(os.path.dirname(__file__) or ".", "..", ".env")
    try:
        if os.path.exists(_dotenv_path):
            with open(_dotenv_path, "r", encoding="utf-8") as _f:
                _lines = _f.readlines()
        else:
            _lines = []
        with open(_dotenv_path, "w", encoding="utf-8") as _f:
            _written = False
            for _line in _lines:
                if _line.startswith("PILOTSTD_API_TOKEN="):
                    _f.write(f"PILOTSTD_API_TOKEN={new_token}\n")
                    _written = True
                else:
                    _f.write(_line)
            if not _written:
                _f.write(f"\nPILOTSTD_API_TOKEN={new_token}\n")
    except OSError:
        pass
    return new_token


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
    """要求当前用户为超级管理员，否则返回 405。"""
    username = get_current_username(request)
    if username != SUPERUSER_USERNAME:
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
MAX_ATTEMPTS = 100  # 5 分钟内最多 100 次失败（压测放宽）
LOCKOUT_SECONDS = 300  # 锁定 5 分钟

# API 全局速率限制：{key: [timestamp, ...]}，key = 用户名 或 IP
_api_rate_limit: dict[str, list[float]] = defaultdict(list)
_api_rate_lock = threading.Lock()  # 保护 _api_rate_limit 并发读写
API_RATE_LIMIT = 1000  # 每分钟最多 1000 次请求（压测放宽）
API_RATE_WINDOW = 60  # 窗口 60 秒


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
def login(
    request: Request,
    username: str = Form(os.environ.get("ADMIN_USERNAME", "admin")),
    password: str = Form(...),
):
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


@router.post("/api/logout")
def logout():
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
    # 更新 last_used_at
    db.execute(
        "UPDATE api_keys SET last_used_at = datetime('now') WHERE key_hash = ?",
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
        # pst_ 前缀 token 验证失败直接 401（不回落 JWT）
        if api_token.startswith("pst_"):
            raise HTTPException(401, "认证失败")
        return False

    def _authenticate_session(self, request) -> None:
        """Origin/Referer 跨源校验 + Cookie JWT 校验 + CSRF 检查。失败直接抛 HTTPException。"""
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
            jwt.decode(token, SECRET, algorithms=["HS256"])
        except JWTError:
            raise HTTPException(401, "认证失败")

        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            csrf_header = request.headers.get(CSRF_HEADER, "")
            csrf_cookie = request.cookies.get("csrf_token", "")
            if not csrf_header or csrf_header != csrf_cookie:
                raise HTTPException(403, "认证失败")

    async def dispatch(self, request, call_next):
        path = request.url.path

        _ensure_static_token_in_db()

        # 白名单 + 非 API 路径放行
        if await self._check_public_path(request, path):
            return await call_next(request)

        # 全局速率限制
        rate_limit_resp = self._check_rate_limit(request)
        if rate_limit_resp:
            return rate_limit_resp

        # API Key 校验
        try:
            if self._authenticate_api_key(request):
                return await call_next(request)
        except HTTPException:
            return JSONResponse({"error": "认证失败"}, 401)

        # Cookie JWT + CSRF 校验
        try:
            self._authenticate_session(request)
        except HTTPException as e:
            return JSONResponse({"error": "认证失败"}, e.status_code)

        return await call_next(request)
