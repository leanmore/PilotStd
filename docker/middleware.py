# 模块：容器/脚本
# 接口中间件定义—从脚本提取，降低主文件复杂度

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 请求体大小上限10，防内存耗尽
MAX_REQUEST_BODY = 10 * 1024 * 1024


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有响应添加安全头，包括 CSP。

    ── 为什么现在可以去掉 `'unsafe-eval'`（NEW-42）──
    原注释说「PrimeVue + Vue 运行时需要 eval」——那是 **Vue 2 / 运行时编译器** 的说法。
    本项目是 Vue 3 + Vite，模板在**构建期预编译**成 render 函数，生产包里不需要
    `new Function` / `eval`。

    实测（2026-11-23，`pnpm run build` 后的 `web/dist/assets/*.js` 共 38 个文件）：
        grep -c "new Function(" → **0**
    故移除 `'unsafe-eval'` 不会破坏运行时，同时消除「同源 SVG 上传 + unsafe-eval」
    组合下的存储型 XSS 放大面（见 NEW-06）。

    `'unsafe-inline'` 保留在 style-src：Vue 的 scoped style 与 PrimeVue 的
    动态样式仍会注入内联 `<style>`；收紧它需要 nonce 方案，属独立改造。
    """

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
            "script-src 'self'; "
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
