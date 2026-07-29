# docker/api/scheduler.py — 调度器状态 API
from datetime import datetime

from fastapi import Depends
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["scheduler"])


@router.get("/api/scheduler/status")
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
                # Phase1: 合并任务执行状态缓存
                "last_run_time": cached["last_run_time"] if cached else None,
                "last_run_status": cached["last_run_status"] if cached else None,
                "last_error_message": cached["last_error_message"] if cached else None,
            }
        )

    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": jobs,
        "timestamp": datetime.now().isoformat(),
    }
