# 容器//脚本—任务队列接口
# 权限：任务管理接口需 admin 角色（@require_role）
import json
import logging

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.time_utils import iso_now

from ..auth import require_role
from ..manager import get_manager_dep


class TaskItem(BaseModel):
    """任务队列单行（列表/详情共用字段）。"""

    task_id: str
    task_type: str
    status: str
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    retry_count: int = 0
    max_retries: int = 3
    queue_name: str = "default"
    error_log: str = ""
    result_json: str = ""
    created_at: str
    started_at: str = ""
    finished_at: str = ""


class TaskListResponse(BaseModel):
    """任务列表分页响应。"""

    total: int
    page: int
    page_size: int
    items: list[TaskItem]


class TaskCreateResponse(BaseModel):
    """任务创建成功响应。"""

    ok: bool
    task_id: str
    status: str


class OkResponse(BaseModel):
    """仅返回 ok 的通用响应。"""

    ok: bool


class PipelineRunItem(BaseModel):
    """管道运行历史单行。"""

    run_id: str
    current_step: str
    status: str
    progress: int
    error_message: str | None = None
    created_at: str
    updated_at: str


class PipelineRunListResponse(BaseModel):
    """管道运行历史分页响应。"""

    total: int
    page: int
    page_size: int
    items: list[PipelineRunItem]


class PipelineRunDetailResponse(PipelineRunItem):
    """管道运行详情（含解析后的 step_results）。"""

    step_results: dict



logger = logging.getLogger(__name__)
router = APIRouter(tags=["tasks"])


@router.get("/api/tasks", response_model=TaskListResponse)
@require_role("admin")
def list_tasks(
    request: Request,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mgr=Depends(get_manager_dep),
):
    """获取任务列表（分页 + 状态筛选）。"""
    q = mgr.task_queue
    tasks = q.get_all(status_filter=status, limit=1000)
    # 简单客户端分页
    filtered = [t for t in tasks if not status or t.get("status") == status]
    total = len(filtered)
    offset = (page - 1) * page_size
    # 构建分页响应，每个任务返回完整字段集合
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "task_id": r["task_id"],
                "task_type": r["task_type"],
                "status": r["status"],
                "total_items": r.get("total_items", 0),
                "completed_items": r.get("completed_items", 0),
                "failed_items": r.get("failed_items", 0),
                "retry_count": r.get("retry_count", 0),
                "max_retries": r.get("max_retries", 3),
                "queue_name": r.get("queue_name", "default"),
                "error_log": r.get("error_log", ""),
                "result_json": r.get("result_json", ""),
                "created_at": r["created_at"],
                "started_at": r.get("started_at", ""),
                "finished_at": r.get("finished_at", ""),
            }
            for r in filtered[offset : offset + page_size]
        ],
    }


@router.get("/api/tasks/runs", response_model=PipelineRunListResponse)
@require_role("admin")
def list_pipeline_runs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mgr=Depends(get_manager_dep),
):
    """查询管道运行历史列表（分页）。"""
    db = mgr.db
    total_row = db.fetchone("SELECT COUNT(*) as cnt FROM pipeline_runs")
    total = total_row["cnt"] if total_row else 0
    offset = (page - 1) * page_size
    rows = db.fetchall(
        "SELECT run_id, current_step, status, progress, error_message, created_at, updated_at "
        "FROM pipeline_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
    return {"total": total, "page": page, "page_size": page_size, "items": rows}


@router.get("/api/tasks/{task_id}", response_model=TaskItem)
@require_role("admin")
def get_task(request: Request, task_id: str, mgr=Depends(get_manager_dep)):
    """获取单个任务的详细信息，包括类型、状态、进度、错误日志和结果。"""
    task = mgr.task_queue.get(task_id)
    if task is None:
        return JSONResponse({"error": "任务不存在"}, 404)
    return {
        "task_id": task.task_id,
        "task_type": task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type),
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "total_items": task.total_items,
        "completed_items": task.completed_items,
        "failed_items": task.failed_items,
        "error_log": task.error_log,
        "result_json": task.result_json,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.post("/api/tasks", response_model=TaskCreateResponse)
@require_role("admin")
def create_task(request: Request, body: dict, mgr=Depends(get_manager_dep)):
    """创建任务并入队。Body: {task_type, total_items?, max_retries?, queue_name?}"""
    from pilotstd.task.models import TaskType

    # 校验任务类型枚举
    task_type_str = body.get("task_type", "")
    try:
        task_type = TaskType(task_type_str)
    except ValueError:
        return JSONResponse({"error": f"未知任务类型: {task_type_str}"}, 400)

    task = mgr.task_queue.enqueue(task_type, total_items=body.get("total_items", 0))
    return {
        "ok": True,
        "task_id": task.task_id,
        "status": task.status.value,
    }


@router.post("/api/tasks/{task_id}/retry", response_model=OkResponse)
@require_role("admin")
def retry_task(request: Request, task_id: str, mgr=Depends(get_manager_dep)):
    """重试失败任务。"""
    task = mgr.task_queue.get(task_id)
    if task is None:
        return JSONResponse({"error": "任务不存在"}, 404)
    # 仅允许重试已失败的任务，运行中/已完成的任务不支持重试
    if task.status.value != "failed":
        return JSONResponse({"error": "只能重试已失败的任务"}, 400)

    from pilotstd.task.models import TaskStatus

    task.status = TaskStatus.PENDING
    task.updated_at = iso_now()
    mgr.task_queue.persist(task)
    return {"ok": True}


@router.post("/api/tasks/{task_id}/cancel", response_model=OkResponse)
@require_role("admin")
def cancel_task(request: Request, task_id: str, mgr=Depends(get_manager_dep)):
    """取消运行中任务。"""
    ok = mgr.task_queue.cancel(task_id)
    return {"ok": ok}


@router.get("/api/tasks/runs/{run_id}", response_model=PipelineRunDetailResponse)
@require_role("admin")
def get_pipeline_run(request: Request, run_id: str, mgr=Depends(get_manager_dep)):
    """查询管道执行状态（扫描→查询→下载→规范化→归档）。"""
    run = mgr.pipeline_store.get(run_id)
    if run is None:
        return JSONResponse({"error": "管道运行记录不存在"}, 404)
    # step_results 存的是 JSON 字符串，解析为对象返回，对齐前端类型
    try:
        step_results = json.loads(run.get("step_results") or "{}")
    except (json.JSONDecodeError, TypeError):
        step_results = {}
    return {
        "run_id": run["run_id"],
        "current_step": run["current_step"],
        "status": run["status"],
        "progress": run["progress"],
        "step_results": step_results,
        "error_message": run["error_message"],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
    }
