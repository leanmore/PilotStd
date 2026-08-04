# 容器//脚本—标准状态查询接口
# ////→状态统计计数
# ///→分页列表（含筛选）
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.db._constants import DatabaseError

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standards"])

_VALID_STATUSES = ("现行", "已废止", "未知")


@router.get("/api/standards/status/stats")
def get_status_stats(mgr=Depends(get_manager_dep)):
    """返回各状态的标准计数（现行/已废止/未知）。"""
    try:
        stats = mgr.standard_service.get_stats()
        by_status = stats["by_status"]
        return {
            "active": by_status.get("现行", 0),
            "inactive": by_status.get("已废止", 0),
            "unknown": by_status.get("未知", 0),
        }
    except DatabaseError as e:
        logger.error("标准状态统计查询失败: %s", e)
        return JSONResponse({"error": f"数据库查询失败: {e}"}, status_code=500)
    except Exception as e:
        logger.exception("标准状态统计查询异常")
        return JSONResponse({"error": f"查询失败: {e}"}, status_code=500)


@router.get("/api/standards/status")
def get_standards_status(
    status: str | None = Query(None, description="现行/已废止/未知"),
    standard_no: str | None = Query(None),
    name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mgr=Depends(get_manager_dep),
):
    """分页查询标准状态列表。"""
    try:
        filters: dict[str, str] = {}
        if status and status in _VALID_STATUSES:
            filters["status"] = status
        keyword = standard_no or name or None
        if keyword:
            filters["keyword"] = keyword

        result = mgr.standard_service.get_list(page=page, size=page_size, filters=filters or None)
        return {
            "total": result["total"],
            "page": result["page"],
            "page_size": result["size"],
            "items": result["items"],
        }
    except DatabaseError as e:
        logger.error("标准状态列表查询失败: %s", e)
        return JSONResponse({"error": f"数据库查询失败: {e}"}, status_code=500)
    except Exception as e:
        logger.exception("标准状态列表查询异常")
        return JSONResponse({"error": f"查询失败: {e}"}, status_code=500)
