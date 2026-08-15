# 容器//脚本—文件监控接口
import logging

from fastapi import Depends, Request
from fastapi.routing import APIRouter

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitor"])


@router.get("/api/monitor/config")
@require_role("admin")
def get_monitor_config(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_config()


@router.put("/api/monitor/config")
@require_role("admin")
def put_monitor_config(request: Request, body: dict, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.set_config(body)


@router.get("/api/monitor/status")
@require_role("admin")
def get_status(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_status()


@router.get("/api/monitor/stats")
@require_role("admin")
def get_stats(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_stats()


@router.post("/api/monitor/start")
@require_role("admin")
def start_monitor(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.start()


@router.post("/api/monitor/stop")
@require_role("admin")
def stop_monitor(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.stop()
