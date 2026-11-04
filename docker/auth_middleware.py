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

from pilotstd import ADMIN_ROLE
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

# 写操作统一要求 admin（D5-1，2026-11-04）：此前仅有部分路由带 @require_role，
# 普通用户可直接 POST /api/validity/run、/api/organize、/api/announcements/{no}/reparse 等，
# 触发全库搬家/重解析/归档。这里在中间件层统一收口（默认拒绝），仅放行下列
# **用户自有数据**的写接口（它们内部都按 session user_id 过滤）：
_USER_WRITE_ALLOWED_EXACT = frozenset(
    {
        "/api/query",  # 查询是 POST，但只读语义
        "/api/favorites",
        "/api/favorites/batch-status",
        "/api/notification/read",
        "/api/notification/config",
        "/api/notification/policy",
        "/api/notification/test",
    }
)
_USER_WRITE_ALLOWED_PREFIX = ("/api/user/",)
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# API Key 强只读：仅放行这一个只读 POST（查询），其余写方法一律 403。
_API_KEY_ALLOWED_POST = frozenset({"/api/query"})


def _user_may_write(path: str) -> bool:
    """普通用户可写的接口白名单（用户自有数据 + 只读查询）。"""
    return path in _USER_WRITE_ALLOWED_EXACT or path.startswith(_USER_WRITE_ALLOWED_PREFIX)


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
                # API Key 强只读：非 GET/HEAD/OPTIONS 一律 403（D5-2）
                if request.method in _WRITE_METHODS and path not in _API_KEY_ALLOWED_POST:
                    return JSONResponse({"error": t("auth.api.forbidden")}, 403)
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

        # 写操作统一要求 admin（D5-1，2026-11-04）：默认拒绝，仅用户自有数据例外。
        role = str(payload.get("role", "user"))
        if request.method in _WRITE_METHODS and role != ADMIN_ROLE and not _user_may_write(path):
            try:
                from pilotstd.core.audit import write_audit

                write_audit(
                    action="ACCESS_DENIED",
                    resource=f"{request.method} {path}",
                    detail={"reason": "write_requires_admin", "role": role},
                    user_id=user_id,
                )
            except Exception as exc:  # noqa: BLE001 — 审计失败不改变拒绝结果，但必须留痕
                logger.warning("audit write failed on write-denied: %s", exc)
            return JSONResponse({"error": t("auth.api.forbidden")}, 403)

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
            except Exception as e:
                import logging

                logging.getLogger("pilotstd.auth").warning("session cleanup failed: %s", e)

    t = threading.Thread(target=_cleanup_loop, daemon=True, name="session-cleanup")
    t.start()
