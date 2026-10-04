# 鉴权中间件（步：自 auth.py 拆出，G-010 余量恢复）
"""鉴权中间件：白名单放行 + Origin/Referer 校验 + Cookie JWT 校验 + API Key 校验 + CSRF 检查。

**为何独立成模块**：它是请求级横切逻辑（~150 行），与路由/依赖注入/登录流程无关；
拆出后 `auth.py` 回到 400 有效行以内。状态与常量取自 `auth_state`（单向依赖，无循环）。
"""

import logging
import threading
import time
from typing import Any, cast

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from pilotstd.i18n import t

from ._static_token import _ensure_static_token_in_db
from .auth_state import (
    API_RATE_LIMIT,
    API_RATE_WINDOW,
    API_TOKEN_HEADER,
    AUTH_WHITELIST,
    COOKIE_NAME,
    CSRF_HEADER,
    SECRET,
    _api_rate_limit,
    _api_rate_lock,
    verify_api_key,
)
from .session_store import get_session_store

logger = logging.getLogger(__name__)


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
                return JSONResponse({"error": t("auth.api.rate_limited")}, 429)
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
            raise HTTPException(401, t("auth.api.unauthorized"))
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
                    raise HTTPException(403, t("auth.api.unauthorized"))
            except Exception:
                raise HTTPException(403, t("auth.api.unauthorized"))

        token = request.cookies.get(COOKIE_NAME)
        if not token:
            raise HTTPException(401, t("auth.api.unauthorized"))
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        except JWTError:
            raise HTTPException(401, t("auth.api.unauthorized"))

        if get_session_store().get(token) is None:
            raise HTTPException(401, t("auth.api.session_expired"))

        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            csrf_header = request.headers.get(CSRF_HEADER, "")
            csrf_cookie = request.cookies.get("csrf_token", "")
            if not csrf_header or csrf_header != csrf_cookie:
                raise HTTPException(403, t("auth.api.unauthorized"))

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
            return JSONResponse({"error": t("auth.api.unauthorized")}, 401)

        # 令牌+跨站伪造防护校验→注入
        try:
            payload = self._authenticate_session(request)
        except HTTPException as e:
            return JSONResponse({"error": t("auth.api.unauthorized")}, e.status_code)

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

                    logging.getLogger("pilotstd.auth").debug(
            t("auth.log.session_cleanup").format(count=removed)
        )
            except Exception:
                pass

    t = threading.Thread(target=_cleanup_loop, daemon=True, name="session-cleanup")
    t.start()
