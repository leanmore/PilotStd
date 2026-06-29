# docker/api/monitor.py — 文件监控 API
import logging

from fastapi import Depends
from fastapi.routing import APIRouter

from ..auth import require_admin
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitor"])


@router.get("/api/monitor/config")
def get_monitor_config(mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_config()


@router.put("/api/monitor/config")
def put_monitor_config(body: dict, mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    return mgr.monitor_service.set_config(body)


@router.get("/api/monitor/status")
def get_status(mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_status()


@router.post("/api/monitor/start")
def start_monitor(mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    return mgr.monitor_service.start()


@router.post("/api/monitor/stop")
def stop_monitor(mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    return mgr.monitor_service.stop()
