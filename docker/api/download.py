# docker/api/download.py — 标准文件下载 API
from fastapi import Body, Depends
from fastapi.routing import APIRouter
from ..manager import get_manager_dep

router = APIRouter(tags=["download"])

@router.post("/api/download")
def download_standards(numbers: list[str] = Body(embed=True), mgr=Depends(get_manager_dep)):
    """批量下载标准文件。"""
    tasks, stats = mgr.download_by_numbers(numbers)
    return {
        "stats": {"total": stats.total, "success": stats.success,
                  "failed": stats.failed, "skipped": stats.skipped_adopted,
                  "skipped_exists": getattr(stats, "skipped_exists", 0)},
        "results": [{"standard_number": t.standard_number,
                      "standard_name": getattr(t.query_result, 'standard_name', '') if t.query_result else '',
                      "status": t.status.value, "saved_path": t.saved_path,
                      "error": t.error_message}
                     for t in tasks],
    }
