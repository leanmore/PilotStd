# 容器//脚本—公告抓取异步接口（19：通过委派）
import logging
from typing import Any

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["announcements"])

# ════════════════════════════════════════════════════════════════ 分隔
# 响应模型：与各路由成功返回的字典键一一对应（错误分支原样返回，不参与校验）
# ════════════════════════════════════════════════════════════════ 分隔


class AnnounceFetchTaskResponse(BaseModel):
    """异步抓取任务受理结果：任务编号与初始状态。"""

    task_id: str
    status: str


class AnnounceTaskStatusResponse(BaseModel):
    """异步抓取任务进度：状态、进度百分比、错误信息与时间戳。"""

    task_id: str
    status: str
    progress: int
    error_msg: str | None = None
    created_at: str
    updated_at: str


class AnnounceTaskResultsResponse(BaseModel):
    """异步抓取任务结果：完成时携带结果数据，未完成时携带提示信息。"""

    task_id: str
    status: str
    data: dict[str, Any] | None = None
    message: str | None = None


@router.post("/api/announcements/fetch", response_model=AnnounceFetchTaskResponse)
@require_role("admin")
def trigger_fetch(request: Request, body: dict | None = None, mgr=Depends(get_manager_dep)):
    """触发异步公告抓取。可选 adapter_name（不传则抓取全部）。"""
    body = body or {}
    adapter_name = body.get("adapter_name", "")
    return mgr._announce_svc.trigger_fetch(adapter_name)


@router.get("/api/announcements/status/{task_id}", response_model=AnnounceTaskStatusResponse)
def get_task_status(task_id: str, mgr=Depends(get_manager_dep)):
    """查询异步抓取任务进度。"""
    result = mgr._announce_svc.get_task_status(task_id)
    if "error" in result:
        return JSONResponse(result, 404)
    return result


@router.get(
    "/api/announcements/results/{task_id}",
    response_model=AnnounceTaskResultsResponse,
    response_model_exclude_none=True,
)
def get_task_results(task_id: str, mgr=Depends(get_manager_dep)):
    """获取异步抓取任务的结果数据。"""
    result = mgr._announce_svc.get_task_results(task_id)
    if "error" in result:
        return JSONResponse(result, 404)
    return result
