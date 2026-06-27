# docker/api/tasks.py — 任务队列 API
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..auth import require_admin
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tasks"])


@router.get("/api/tasks")
def list_tasks(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mgr=Depends(get_manager_dep),
):
    """获取任务列表（分页 + 状态筛选）。"""
    q = mgr.task_queue
    where = f"WHERE status='{status}'" if status else ""
    count_row = q._db.fetchone(f"SELECT COUNT(*) as cnt FROM task_queue {where}")
    total = count_row["cnt"] if count_row else 0
    offset = (page - 1) * page_size
    rows = q._db.fetchall(
        f"SELECT * FROM task_queue {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
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
            for r in rows
        ],
    }


@router.get("/api/tasks/{task_id}")
def get_task(task_id: str, mgr=Depends(get_manager_dep)):
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


@router.post("/api/tasks")
def create_task(body: dict, mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """创建任务并入队。Body: {task_type, total_items?, max_retries?, queue_name?}"""
    from pilotstd.task.models import TaskType

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


@router.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str, mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """重试失败任务。"""
    task = mgr.task_queue.get(task_id)
    if task is None:
        return JSONResponse({"error": "任务不存在"}, 404)
    if task.status.value != "failed":
        return JSONResponse({"error": "只能重试已失败的任务"}, 400)

    from pilotstd.task.models import TaskStatus

    task.status = TaskStatus.PENDING
    task.updated_at = __import__("datetime").datetime.now().isoformat()
    mgr.task_queue._persist(task)
    return {"ok": True}


@router.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str, mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """取消运行中任务。"""
    ok = mgr.task_queue.cancel(task_id)
    return {"ok": ok}
