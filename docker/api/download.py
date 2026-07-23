# docker/api/download.py — 标准文件下载 API
from typing import Optional

from fastapi import Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["download"])


@router.post("/api/download")
def download_standards(
    numbers: list[str] = Body(embed=True),
    run_id: str = Body(..., embed=True),
    mgr=Depends(get_manager_dep),
):
    """批量下载标准文件。"""
    # 更新管道：进入下载阶段
    try:
        mgr.pipeline_store.update_step(
            run_id,
            "download",
            "running",
            40,
            step_results={"count": len(numbers)},
        )
    except Exception:
        pass

    try:
        tasks, stats = mgr.download_by_numbers(numbers)
        mgr.pipeline_store.update_step(
            run_id,
            "download",
            "completed",
            60,
            step_results={"success": stats.success, "failed": stats.failed},
        )
    except Exception as exc:
        mgr.pipeline_store.update_step(
            run_id,
            "download",
            "failed",
            40,
            error=str(exc),
        )
        raise

    return {
        "stats": {
            "total": stats.total,
            "success": stats.success,
            "failed": stats.failed,
            "skipped": stats.skipped_adopted,
            "skipped_exists": getattr(stats, "skipped_exists", 0),
        },
        "results": [
            {
                "standard_number": t.standard_number,
                "standard_name": getattr(t.query_result, "standard_name", "") if t.query_result else "",
                "status": t.status.value,
                "saved_path": t.saved_path,
                "error": t.error_message,
            }
            for t in tasks
        ],
    }


@router.post("/api/download/import")
async def import_downloads(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    mgr=Depends(get_manager_dep),
):
    """Q24: 手动导入下载列表。text 与 file 互斥，仅支持一个输入源。"""
    from pilotstd.core.download_utils import parse_download_sources

    if not text and not file:
        raise HTTPException(400, "必须提供 text 或 file 之一")
    if text and file:
        raise HTTPException(400, "text 与 file 不可同时提供")

    # 文件上传：读取内容后转为文本
    if file:
        content = await file.read()
        text = content.decode("utf-8")

    parsed = parse_download_sources(text=text)

    # 无效标准号直接返回，不提交下载
    if parsed["invalid"] and not parsed["valid"]:
        return {
            "valid": parsed["valid"],
            "invalid": parsed["invalid"],
            "duplicates": parsed["duplicates"],
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "results": [],
        }

    # 提交有效标准号到下载引擎
    tasks, stats = mgr.download_by_numbers(parsed["valid"])
    return {
        "valid": parsed["valid"],
        "invalid": parsed["invalid"],
        "duplicates": parsed["duplicates"],
        "total": stats.total,
        "success": stats.success,
        "failed": stats.failed,
        "skipped": getattr(stats, "skipped_adopted", 0) + getattr(stats, "skipped_exists", 0),
        "results": [
            {
                "standard_number": t.standard_number,
                "standard_name": getattr(t.query_result, "standard_name", "") if t.query_result else "",
                "status": t.status.value,
                "saved_path": t.saved_path,
                "error": t.error_message,
            }
            for t in tasks
        ],
    }
