# 容器//脚本—文件监控接口
import logging

from fastapi import Depends
from fastapi.routing import APIRouter

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitor"])


@require_role("admin")
@router.get("/api/monitor/config")
def get_monitor_config(mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_config()


@require_role("admin")
@router.put("/api/monitor/config")
def put_monitor_config(body: dict, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.set_config(body)


@require_role("admin")
@router.get("/api/monitor/status")
def get_status(mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_status()


@require_role("admin")
@router.get("/api/monitor/stats")
def get_stats(mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_stats()


@require_role("admin")
@router.post("/api/monitor/start")
def start_monitor(mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.start()


@require_role("admin")
@router.post("/api/monitor/stop")
def stop_monitor(mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.stop()
