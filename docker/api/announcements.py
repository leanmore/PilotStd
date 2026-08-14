# 容器//脚本—公告抓取异步接口（19：通过委派）
import logging

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["announcements"])


@router.post("/api/announcements/fetch")
def trigger_fetch(body: dict | None = None, mgr=Depends(get_manager_dep)):
    """触发异步公告抓取。可选 adapter_name（不传则抓取全部）。"""
    body = body or {}
    adapter_name = body.get("adapter_name", "")
    return mgr._announce_svc.trigger_fetch(adapter_name)


@router.get("/api/announcements/status/{task_id}")
def get_task_status(task_id: str, mgr=Depends(get_manager_dep)):
    """查询异步抓取任务进度。"""
    result = mgr._announce_svc.get_task_status(task_id)
    if "error" in result:
        return JSONResponse(result, 404)
    return result


@router.get("/api/announcements/results/{task_id}")
def get_task_results(task_id: str, mgr=Depends(get_manager_dep)):
    """获取异步抓取任务的结果数据。"""
    result = mgr._announce_svc.get_task_results(task_id)
    if "error" in result:
        return JSONResponse(result, 404)
    return result
