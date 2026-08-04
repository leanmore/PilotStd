# 模块：容器/脚本
# 接口中间件定义—从脚本提取，降低主文件复杂度

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 请求体大小上限10，防内存耗尽
MAX_REQUEST_BODY = 10 * 1024 * 1024


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有响应添加安全头，包括 CSP（PrimeVue + Vue 运行时需要 eval 和内联样式）。"""

    async def dispatch(self, request, call_next):
        """拦截每个响应，注入安全头（CSP、HSTS、X-Frame-Options 等）。"""
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("X-XSS-Protection", "1; mode=block")
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'",
        )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """限制请求体大小，超限返回 413。"""

    async def dispatch(self, request, call_next):
        """检查请求体 Content-Length，超限（>10MB）直接返回 413，否则放行。"""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY:
            return JSONResponse({"error": "请求体过大"}, status_code=413)
        return await call_next(request)
