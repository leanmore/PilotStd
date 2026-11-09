# 模块：容器/API/健康检查端点
# 无鉴权（仅生产环境限制内网），用于部署后快速验证核心服务可用性
import ipaddress
import logging
import os
import shutil

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# 允许的私有网络段（RFC1918 + loopback）
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

DISK_THRESHOLD_MB = 500.0
SCHEDULER_TIMEOUT_SECONDS = 180.0


def _is_private_ip(ip_str: str) -> bool | None:
    """检查 IP 是否在 RFC1918 或 loopback 段内。

    Returns:
        True / False；IP 无法解析时返回 **None（第三态 unknown）**——调用方不得把它
        当作「公网」处理（U-3/U-4 批 2a：非法 IP 原被静默当成公网）。
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        # i18n-allow: 内部运维日志
        logger.warning("IP 格式非法，健康检查来源判定为 unknown: %s", ip_str)
        return None


def _check_database_read(mgr) -> bool:
    """数据库读连通性：SELECT 1。"""
    try:
        result = mgr.db.fetchone("SELECT 1 AS ok")
        return result is not None and result.get("ok") == 1
    except Exception:
        logger.warning("健康检查: 数据库读取不可用", exc_info=True)
        return False


def _check_database_write(mgr) -> bool:
    """数据库写连通性：TEMP 表写入/删除（不触碰业务表）。"""
    try:
        mgr.db.execute("CREATE TEMP TABLE IF NOT EXISTS _health_probe (x INTEGER)")
        mgr.db.execute("INSERT INTO _health_probe (x) VALUES (1)")
        mgr.db.execute("DELETE FROM _health_probe")
        return True
    except Exception:
        # i18n-allow: 内部日志
        logger.warning("健康检查: 数据库写入不可用", exc_info=True)
        return False


def _check_monitor_service(mgr) -> bool:
    """检查 monitor_service 是否已初始化。"""
    return hasattr(mgr, "monitor_service") and mgr.monitor_service is not None


def _check_parser(mgr) -> bool:
    """检查 parser 是否已初始化。"""
    return hasattr(mgr, "parser") and mgr.parser is not None


def _get_schema_version(mgr) -> int:
    """读取当前库 schema 版本；用于部署后确认迁移是否真的执行。"""
    try:
        return int(mgr.db.schema_version)
    except Exception:
        # i18n-allow: 内部日志；读失败不应让健康检查整体 500
        logger.warning("健康检查: schema 版本读取失败", exc_info=True)
        return 0


def _check_disk(mgr) -> dict:
    """数据目录磁盘余量；低于 500MB 视为 degraded。"""
    data_dir = os.path.dirname(os.path.abspath(mgr.db.path))
    try:
        usage = shutil.disk_usage(data_dir)
        free_mb = round(usage.free / (1024 * 1024), 1)
        return {"free_mb": free_mb, "threshold_mb": DISK_THRESHOLD_MB, "ok": free_mb >= DISK_THRESHOLD_MB}
    except OSError:
        # i18n-allow: 内部日志
        logger.warning("健康检查: 磁盘余量读取失败", exc_info=True)
        return {"free_mb": 0.0, "threshold_mb": DISK_THRESHOLD_MB, "ok": False}


def _check_scheduler(mgr) -> dict:
    """scheduler_lock 心跳；缺失或超过 180s 未更新视为后台任务假死。"""
    try:
        row = mgr.db.fetchone("SELECT heartbeat_at FROM scheduler_lock WHERE id=1")
        if not row or not row.get("heartbeat_at"):
            return {"heartbeat_at": None, "age_seconds": None, "ok": False}
        from pilotstd.core.time_utils import now, parse_iso

        hb = parse_iso(str(row["heartbeat_at"]))
        age = (now() - hb).total_seconds() if hb else None
        return {
            "heartbeat_at": str(row["heartbeat_at"]),
            "age_seconds": round(age, 1) if age is not None else None,
            "ok": age is not None and age <= SCHEDULER_TIMEOUT_SECONDS,
        }
    except Exception:
        # i18n-allow: 内部日志
        logger.warning("健康检查: 调度器心跳读取失败", exc_info=True)
        return {"heartbeat_at": None, "age_seconds": None, "ok": False}


class HealthServices(BaseModel):
    """兼容旧字段：数据库、监控服务、解析器可用性。"""

    database: bool
    monitor_service: bool
    parser: bool


class HealthDisk(BaseModel):
    """数据目录磁盘余量。"""

    free_mb: float
    threshold_mb: float
    ok: bool


class HealthScheduler(BaseModel):
    """调度器心跳。"""

    heartbeat_at: str | None
    age_seconds: float | None
    ok: bool


class HealthDatabase(BaseModel):
    """数据库读/写连通性。"""

    read: bool
    write: bool


class HealthChecks(BaseModel):
    """真实健康指标集合。"""

    disk: HealthDisk
    scheduler: HealthScheduler
    database_rw: HealthDatabase


class HealthCheckResponse(BaseModel):
    """健康检查响应。"""

    status: str
    timestamp: str
    version: str
    schema_version: int
    services: HealthServices
    checks: HealthChecks


@router.get("/api/health", response_model=HealthCheckResponse)
def health_check(request: Request):
    """健康检查：数据库读写、磁盘余量、调度器心跳。

    状态码：200=ok，207=degraded（磁盘/心跳异常但服务可用），500=down（数据库不可读写）。
    """
    from ..manager import get_manager

    env = os.getenv("ENV", "development")
    if env == "production":
        client_host = request.client.host if request.client else "unknown"
        is_private = _is_private_ip(client_host)
        if is_private is None:
            # fail-safe：IP 解析失败（unknown）按「非内部 IP」拒绝，绝不因解析不了而放行
            # i18n-allow: 内部运维日志
            logger.warning("客户端 IP 格式非法，按非内部 IP 处理（拒绝）: %s", client_host)
            raise HTTPException(status_code=403, detail="Forbidden")
        if is_private is False:
            raise HTTPException(status_code=403, detail="Forbidden")

    mgr = get_manager()
    db_read = _check_database_read(mgr)
    db_write = _check_database_write(mgr)
    schema_version = _get_schema_version(mgr)
    disk = _check_disk(mgr)
    scheduler = _check_scheduler(mgr)

    services = {
        "database": db_read,
        "monitor_service": _check_monitor_service(mgr),
        "parser": _check_parser(mgr),
    }
    if not (db_read and db_write):
        status, code = "down", 500
    elif not (disk["ok"] and scheduler["ok"]):
        status, code = "degraded", 207
    else:
        status, code = "ok", 200

    from pilotstd.core.time_utils import iso_now

    return JSONResponse(
        status_code=code,
        content={
            "status": status,
            "timestamp": iso_now(),
            "version": os.getenv("APP_VERSION", "unknown"),
            "schema_version": schema_version,
            "services": services,
            "checks": {"disk": disk, "scheduler": scheduler, "database_rw": {"read": db_read, "write": db_write}},
        },
    )
