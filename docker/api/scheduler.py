# 容器//调度器脚本—调度器状态接口
from typing import Any

from fastapi import Depends, Query
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.time_utils import iso_now

from ..manager import get_manager_dep

router = APIRouter(tags=["scheduler"])

# 响应模型：任务条目、调度状态、执行历史与聚合统计


class SchedulerJobItem(BaseModel):
    """调度任务条目：标识、下次执行时间、触发器与最近执行结果。"""

    id: str
    next_run_time: str | None
    trigger: str
    pending: bool
    last_run_time: str | None
    last_run_status: str | None
    last_error_message: str | None


class SchedulerStatusResponse(BaseModel):
    """调度器状态响应：运行标志、任务数量、任务列表与时间戳。"""

    running: bool
    job_count: int
    jobs: list[SchedulerJobItem]
    timestamp: str


class SchedulerHistoryResponse(BaseModel):
    """调度执行历史分页响应：总数、记录列表、页码与每页条数。"""

    total: int
    items: list[dict[str, Any]]
    page: int | None = None
    size: int | None = None


class SchedulerHistoryStatsResponse(BaseModel):
    """调度任务聚合统计响应：任务维度的成功率与耗时列表。"""

    tasks: list[dict[str, Any]]


@router.get("/api/scheduler/status", response_model=SchedulerStatusResponse)
def get_scheduler_status(mgr=Depends(get_manager_dep)):
    """获取调度器状态：任务列表、下次执行时间、运行状态 + 最近执行结果。"""
    from docker.scheduler import scheduler
    from pilotstd.core.task_status import get_all_task_status

    task_status_map = get_all_task_status()
    jobs = []
    for job in scheduler.get_jobs():
        cached = task_status_map.get(job.id)
        jobs.append(
            {
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "pending": bool(job.pending),
                # 阶段1:合并任务执行状态缓存
                "last_run_time": cached["last_run_time"] if cached else None,
                "last_run_status": cached["last_run_status"] if cached else None,
                "last_error_message": cached["last_error_message"] if cached else None,
            }
        )

    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": jobs,
        "timestamp": iso_now(),
    }


@router.get("/api/scheduler/history", response_model=SchedulerHistoryResponse, response_model_exclude_unset=True)
def get_scheduler_history(
    task_name: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """分页查询任务执行历史，支持按 task_name 过滤。"""
    from pilotstd.core.task_history import get_task_history

    name = task_name.strip() if task_name else None
    return get_task_history(task_name=name, page=page, size=size)


@router.get("/api/scheduler/history/stats", response_model=SchedulerHistoryStatsResponse)
def get_scheduler_history_stats():
    """获取每个任务的聚合统计：成功率、平均耗时、最近错误。"""
    from pilotstd.core.task_history import get_task_stats

    return {"tasks": get_task_stats()}
