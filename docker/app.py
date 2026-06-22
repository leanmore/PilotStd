# docker/app.py — FastAPI 入口（模块组装 + 安全头 + 健康检查 + 请求体限制）
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .api.announce import router as announce_router
from .api.announce_lookup import router as announce_lookup_router
from .api.api_keys import router as api_keys_router
from .api.archive import router as archive_router
from .api.download import router as download_router
from .api.logs import router as logs_router
from .api.normalize import router as normalize_router
from .api.organize import router as organize_router
from .api.pending import router as pending_router
from .api.query import router as query_router
from .api.scan import router as scan_router
from .api.settings import router as settings_router
from .api.stats import router as stats_router
from .api.system import router as system_router
from .api.upload import router as upload_router
from .api.users import router as users_router
from .auth import AuthMiddleware
from .auth import router as auth_router
from .scheduler import register_job_func, start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)

# 请求体大小上限 10MB，防内存耗尽
MAX_REQUEST_BODY = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：延迟初始化业务模块 → 注册定时任务 → 启动调度器 → 关闭时停止。"""
    # 日志持久化：Docker 容器需显式初始化 LoggerManager（与 Windows GUI 对齐）
    from pilotstd.core.logger import LoggerManager

    LoggerManager(level=logging.INFO)

    # StandardManager 初始化较重（DB连接/适配器加载），在 lifespan 内延迟执行
    from .manager import get_manager as _get_mgr

    _cron_mgr = _get_mgr()  # 触发初始化，之后所有 API 模块共享此实例
    register_job_func("auto_scan", lambda: _cron_mgr.scan_and_index())
    register_job_func("auto_query", lambda: _cron_mgr.recheck_updates())
    from .api.announce import check_announce

    register_job_func("auto_announce", check_announce)
    start_scheduler()
    yield
    # 关闭时释放资源
    stop_scheduler()
    _cron_mgr.shutdown()


from pilotstd import __version__ as _app_version  # noqa: E402

app = FastAPI(title="PilotStd API", version=_app_version, lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理：捕获所有未处理异常，写日志 + 返回 500。"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(
        {"error": "服务器内部错误", "detail": str(exc)}, status_code=500
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有响应添加安全头，包括 CSP（PrimeVue + Vue 运行时需要 eval 和内联样式）。"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("X-XSS-Protection", "1; mode=block")
        headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
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
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY:
            return JSONResponse({"error": "请求体过大"}, status_code=413)
        return await call_next(request)


# 中间件注册顺序：安全头 → 请求体限制 → 鉴权
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(AuthMiddleware)

# 注册 API 路由
app.include_router(auth_router)
app.include_router(scan_router)
app.include_router(query_router)
app.include_router(download_router)
app.include_router(organize_router)
app.include_router(announce_router)
app.include_router(announce_lookup_router)
app.include_router(api_keys_router)
app.include_router(pending_router)
app.include_router(settings_router)
app.include_router(stats_router)
app.include_router(normalize_router)
app.include_router(archive_router)
app.include_router(users_router)
app.include_router(upload_router)
app.include_router(logs_router)
app.include_router(system_router)


# 健康检查端点（Docker HEALTHCHECK 使用）
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": _app_version,
    }


# 挂载 Vue 静态文件 + SPA 回退
_DOCKER_DIR = os.path.dirname(os.path.abspath(__file__))  # docker/ 目录
_PROJ_ROOT = os.path.dirname(_DOCKER_DIR)  # 项目根目录
DIST = os.path.join(_PROJ_ROOT, "web", "dist")
if os.path.isdir(os.path.join(DIST, "assets")):
    app.mount(
        "/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets"
    )


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """SPA 回退路由：非 API 路径返回前端 index.html。"""
    if full_path.startswith("api/"):
        raise HTTPException(404)
    index = os.path.join(DIST, "index.html")
    return FileResponse(index) if os.path.exists(index) else {"message": "前端未构建"}
