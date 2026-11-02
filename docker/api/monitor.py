# 容器//脚本—文件监控接口
import logging

from fastapi import Depends, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel, field_validator

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitor"])

# 响应模型：配置读写、运行状态、当日统计与启停结果


class MonitorConfigResponse(BaseModel):
    """文件监控配置响应：启用开关、监控路径、延迟与匹配规则。"""

    enabled: bool
    watch_path: str
    delay_seconds: int
    recursive: bool
    file_patterns: list[str]
    ignore_patterns: list[str]
    auto_archive: bool


class MonitorOkResponse(BaseModel):
    """文件监控写操作结果：仅表示是否成功。"""

    ok: bool


class MonitorStatusResponse(BaseModel):
    """文件监控运行状态响应：运行标志、路径与今日统计。"""

    running: bool
    enabled: bool
    watch_path: str
    delay_seconds: int
    last_processed: str
    processed_today: int
    success_today: int
    failed_today: int

    @field_validator("watch_path", "last_processed", mode="before")
    @classmethod
    def _string_or_empty(cls, value):
        """非字符串按空串处理，避免单个字段异常拖垮状态接口。"""
        return value if isinstance(value, str) else ""


class MonitorStatsResponse(BaseModel):
    """文件监控当日统计响应：处理、成功与失败数量。"""

    date: str
    processed: int
    success: int
    failed: int


class MonitorStateResponse(BaseModel):
    """文件监控启停结果：是否成功及当前运行状态。"""

    ok: bool
    running: bool


# 路由：配置读写、状态查询、统计查询与启停控制
@router.get("/api/monitor/config", response_model=MonitorConfigResponse)
@require_role("admin")
def get_monitor_config(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_config()


@router.put("/api/monitor/config", response_model=MonitorOkResponse)
@require_role("admin")
def put_monitor_config(request: Request, body: dict, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.set_config(body)


@router.get("/api/monitor/status", response_model=MonitorStatusResponse)
@require_role("admin")
def get_status(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_status()


@router.get("/api/monitor/stats", response_model=MonitorStatsResponse)
@require_role("admin")
def get_stats(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.get_stats()


@router.post("/api/monitor/start", response_model=MonitorStateResponse)
@require_role("admin")
def start_monitor(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.start()


@router.post("/api/monitor/stop", response_model=MonitorStateResponse)
@require_role("admin")
def stop_monitor(request: Request, mgr=Depends(get_manager_dep)):
    return mgr.monitor_service.stop()
