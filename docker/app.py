# docker/app.py — FastAPI 入口（模块组装 + 安全头 + 健康检查 + 请求体限制）
# ruff: noqa: E402  — load_dotenv() 必须在其他模块导入前执行
import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# 加载 .env 文件（Docker 容器内路径 /app/.env，通过卷挂载注入）
load_dotenv(os.path.join(os.path.dirname(__file__) or ".", "..", ".env"))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.adapter import router as adapter_router
from .api.announce import router as announce_router
from .api.announce_lookup import router as announce_lookup_router
from .api.announcements import router as announcements_router
from .api.api_keys import router as api_keys_router
from .api.archive import router as archive_router
from .api.auto import router as auto_router
from .api.backup import router as backup_router
from .api.cache import router as cache_router
from .api.download import router as download_router
from .api.export import router as export_router
from .api.logs import router as logs_router
from .api.monitor import router as monitor_router
from .api.normalize import router as normalize_router
from .api.notification import router as notification_router
from .api.organize import router as organize_router
from .api.pending import router as pending_router
from .api.quality import router as quality_router
from .api.query import router as query_router
from .api.scan import router as scan_router
from .api.scheduler import router as scheduler_router
from .api.settings import router as settings_router
from .api.stats import router as stats_router
from .api.system import router as system_router
from .api.tasks import router as tasks_router
from .api.upload import router as upload_router
from .api.user import router as user_layout_router
from .api.users import router as users_router
from .api.validity import router as validity_router
from .api.wechat_ip import router as wechat_ip_router
from .auth import AuthMiddleware
from .auth import router as auth_router
from .middleware import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from .scheduler import _backup_database, register_job_func, start_scheduler, stop_scheduler
from .websocket import websocket_endpoint

logger = logging.getLogger(__name__)


def _clean_zombie_tasks() -> None:
    """清理启动前遗留的僵尸抓取任务（status='running'/'pending' → failed）。"""
    try:
        from pilotstd.core.config import get_db_path
        from pilotstd.core.db import Database

        db = Database(get_db_path())
        db.execute(
            "UPDATE fetch_task SET status='failed', error_msg='任务被中断（服务重启）' "
            "WHERE status IN ('running', 'pending')"
        )
        db.close()
    except Exception:
        pass


def _start_all_schedulers(_cron_mgr) -> None:
    """注册定时任务并启动所有调度器（APScheduler + 任务调度器 + 监控 + 可信IP）。"""
    register_job_func("auto_scan", lambda: _cron_mgr.scan_and_index())
    from .api.announce import check_announce

    register_job_func("auto_announce", check_announce)
    register_job_func("auto_backup", lambda: _backup_database(notification_mgr=_cron_mgr.notification_mgr))
    from .scheduler import _cleanup_notification_logs

    register_job_func(
        "notification_cleanup",
        lambda: _cleanup_notification_logs(notification_mgr=_cron_mgr.notification_mgr),
    )
    start_scheduler()

    # 任务调度器自动启动
    try:
        from pilotstd.task.scheduler import get_scheduler as get_task_scheduler

        get_task_scheduler().set_queue(_cron_mgr.task_queue)
        get_task_scheduler().start()
    except Exception:
        pass

    # 文件监控自动启动
    try:
        _cron_mgr.monitor_service.start_scheduler()
    except Exception:
        pass

    # 企业微信可信 IP 自动更新（独立线程，不占用 APScheduler）
    try:
        if _cron_mgr.cfg.get("wechat_ip.enabled", False):
            _cron_mgr.wechat_ip_service.start_scheduler()
            interval = int(_cron_mgr.cfg.get("wechat_ip.interval_hours", 6))
            logger.info("可信 IP 自动更新已启动 (间隔=%dh)", interval)
    except Exception:
        pass


def _shutdown_cleanup(_cron_mgr) -> None:
    """关闭时释放所有资源（调度器、服务、线程）。"""
    stop_scheduler()
    _cron_mgr.shutdown()

    try:
        _cron_mgr.monitor_service.stop_scheduler()
    except Exception:
        pass

    try:
        _cron_mgr.wechat_ip_service.stop_scheduler()
    except Exception:
        pass

    try:
        from pilotstd.task.scheduler import get_scheduler as get_task_scheduler

        get_task_scheduler().stop()
    except Exception:
        pass


def _run_backfill_if_needed(mgr) -> None:
    """公告历史数据回填（幂等，仅执行一次）。"""
    from pilotstd.announcement.adapters.samr_db import SamrDbCrawler
    from pilotstd.announcement.adapters.samr_gb import SamrGbCrawler
    from pilotstd.announcement.adapters.samr_hb import SamrHbCrawler

    from .backfill_announce import run_backfill

    _adapters = {"gb": SamrGbCrawler(), "hb": SamrHbCrawler(), "db": SamrDbCrawler()}
    run_backfill(mgr.db, _adapters)


def _setup_ws_broadcast(mgr) -> None:
    """注入 WebSocket 广播回调。"""

    def _ws_broadcast_callback(
        event_type: str,
        title: str,
        body: str,
        level: str,
        link: str | None = None,
        icon: str | None = None,
        aggregated_count: int = 1,
    ) -> None:
        try:
            from datetime import datetime

            from .websocket import get_ws_manager

            ws_manager = get_ws_manager()
            if ws_manager.connection_count == 0:
                return
            import asyncio

            payload = {
                "event_type": event_type,
                "title": title,
                "body": body,
                "level": level,
                "sent_at": datetime.now().isoformat(),
                "link": link,
                "icon": icon,
                "aggregated_count": aggregated_count,
            }
            try:
                asyncio.create_task(ws_manager.broadcast(payload))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(ws_manager.broadcast(payload))
                loop.close()
        except Exception:
            pass

    mgr.notification_mgr._ws_broadcast = _ws_broadcast_callback


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：延迟初始化业务模块 → 注册定时任务 → 启动调度器 → 关闭时停止。"""
    # ── SUPERUSER 启动校验（守卫从 pilotstd/__init__.py 迁移至此） ──
    _su = os.getenv("SUPERUSER")
    if not _su:
        print("FATAL: SUPERUSER environment variable is not set", file=sys.stderr)
        sys.exit(1)
    if _su.lower() == "admin":
        print("FATAL: SUPERUSER cannot be 'admin', please use a different username", file=sys.stderr)
        sys.exit(1)

    # 日志持久化：Docker 容器需显式初始化 LoggerManager（与 Windows GUI 对齐）
    from pilotstd.core.logger import LoggerManager

    LoggerManager(level=logging.INFO)

    # 启动会话清理后台线程
    from .auth import _start_session_cleanup

    _start_session_cleanup()

    # 清理启动前遗留的僵尸抓取任务
    _clean_zombie_tasks()

    # StandardManager 初始化较重（DB连接/适配器加载），在 lifespan 内延迟执行
    from .manager import get_manager as _get_mgr

    _cron_mgr = _get_mgr()

    _setup_ws_broadcast(_cron_mgr)

    _start_all_schedulers(_cron_mgr)

    # 公告历史数据回填（幂等，仅执行一次）
    try:
        _run_backfill_if_needed(_cron_mgr)
    except Exception:
        logger.warning("公告历史数据回填失败", exc_info=True)

    yield
    # 优雅关闭：刷新聚合缓冲（防止通知丢失）
    if hasattr(_cron_mgr.notification_mgr, "shutdown"):
        _cron_mgr.notification_mgr.shutdown()
    # 关闭时释放资源
    _shutdown_cleanup(_cron_mgr)


from pilotstd import __version__ as _app_version  # noqa: E402

app = FastAPI(title="PilotStd API", version=_app_version, lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理：捕获所有未处理异常，写日志 + 返回 500。"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse({"error": "服务器内部错误", "detail": str(exc)}, status_code=500)


# 中间件注册顺序：安全头 → 请求体限制 → 鉴权
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(AuthMiddleware)

# ── 鉴权与用户 ──
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(user_layout_router)
app.include_router(api_keys_router)

# ── 核心业务 ──
app.include_router(query_router)
app.include_router(download_router)
app.include_router(scan_router)
app.include_router(organize_router)
app.include_router(archive_router)
app.include_router(stats_router)
app.include_router(normalize_router)

# ── 公告 ──
app.include_router(announce_router)
app.include_router(announce_lookup_router)
app.include_router(announcements_router)

# ── 管理与配置 ──
app.include_router(settings_router)
app.include_router(notification_router)
app.include_router(adapter_router)
app.include_router(scheduler_router)
app.include_router(backup_router)
app.include_router(export_router)
app.include_router(quality_router)
app.include_router(pending_router)
app.include_router(validity_router)
app.include_router(wechat_ip_router)
app.include_router(cache_router)

# ── 系统与监控 ──
app.include_router(system_router)
app.include_router(monitor_router)
app.include_router(logs_router)

# ── 文件与自动化 ──
app.include_router(upload_router)
app.include_router(tasks_router)
app.include_router(auto_router)


# ── WebSocket ──
@app.websocket("/api/notification/ws")
async def notification_websocket(websocket):
    await websocket_endpoint(websocket)


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
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """SPA 回退路由：非 API 路径返回前端 index.html。"""
    if full_path.startswith("api/"):
        raise HTTPException(404)
    index = os.path.join(DIST, "index.html")
    return FileResponse(index) if os.path.exists(index) else {"message": "前端未构建"}
