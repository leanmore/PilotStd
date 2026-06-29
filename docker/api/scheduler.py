# docker/api/scheduler.py — 调度器状态 API
from datetime import datetime

from fastapi import Depends
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["scheduler"])


@router.get("/api/scheduler/status")
def get_scheduler_status(mgr=Depends(get_manager_dep)):
    """获取调度器状态：任务列表、下次执行时间、运行状态。"""
    from docker.scheduler import scheduler

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "pending": bool(job.pending),
            }
        )

    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": jobs,
        "timestamp": datetime.now().isoformat(),
    }
