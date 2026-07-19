# docker/api/health.py — 健康检查端点
# 无鉴权（仅生产环境限制内网IP），用于部署后快速验证核心服务可用性
import ipaddress
import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# 允许的私有网络段（RFC1918 + loopback）
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


def _is_private_ip(ip_str: str) -> bool:
    """检查 IP 是否在 RFC1918 或 loopback 段内。"""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def _check_database(mgr) -> bool:
    """检查数据库连接：执行 SELECT 1。"""
    try:
        result = mgr.db.fetchone("SELECT 1 AS ok")
        return result is not None and result.get("ok") == 1
    except Exception:
        logger.warning("健康检查: 数据库不可用", exc_info=True)
        return False


def _check_monitor_service(mgr) -> bool:
    """检查 monitor_service 是否已初始化。"""
    return hasattr(mgr, "monitor_service") and mgr.monitor_service is not None


def _check_parser(mgr) -> bool:
    """检查 parser 是否已初始化。"""
    return hasattr(mgr, "parser") and mgr.parser is not None


@router.get("/api/health")
def health_check(request: Request):
    """健康检查：返回各服务状态、版本号、时间戳。

    生产环境仅允许内网 IP 访问，外网返回 403。
    """
    from ..manager import get_manager

    env = os.getenv("ENV", "development")
    if env == "production":
        client_host = request.client.host if request.client else "unknown"
        if not _is_private_ip(client_host):
            raise HTTPException(status_code=403, detail="Forbidden")

    mgr = get_manager()
    services = {
        "database": _check_database(mgr),
        "monitor_service": _check_monitor_service(mgr),
        "parser": _check_parser(mgr),
    }

    status = "ok" if all(services.values()) else "degraded"
    return JSONResponse(
        content={
            "status": status,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "version": os.getenv("APP_VERSION", "unknown"),
            "services": services,
        }
    )
