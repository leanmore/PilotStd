# 容器//脚本—标准状态查询接口
# ////→状态统计计数
# ///→分页列表（含筛选）
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core import status as status_dict
from pilotstd.core.db._constants import DatabaseError
from pilotstd.core.status import Status

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standards"])

# 对外 API 的合法状态取值（由状态字典派生；A 阶段 #32-A 建立、C 阶段继续作为契约常量）
_VALID_STATUSES = status_dict.API_VALID_STATUSES


@router.get("/api/standards/status/stats")
def get_status_stats(mgr=Depends(get_manager_dep)):
    """返回各状态的标准计数（现行/已废止/未知）。"""
    try:
        stats = mgr.standard_service.get_stats()
        by_status = stats["by_status"]
        return {
            "active": by_status.get(Status.ACTIVE.value, 0),
            "inactive": by_status.get(Status.WITHDRAWN_NORMALIZED.value, 0),
            "unknown": by_status.get(Status.UNKNOWN.value, 0),
        }
    except DatabaseError as e:
        logger.error("标准状态统计查询失败: %s", e)
        return JSONResponse({"error": f"数据库查询失败: {e}"}, status_code=500)
    except Exception as e:
        logger.exception("标准状态统计查询异常")
        return JSONResponse({"error": f"查询失败: {e}"}, status_code=500)


@router.get("/api/standards/status")
def get_standards_status(
    status: str | None = Query(None, description="英文键（active/withdrawn/unknown）或历史中文值（现行/已废止/未知）"),
    standard_no: str | None = Query(None),
    name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mgr=Depends(get_manager_dep),
):
    """分页查询标准状态列表。

    **响应契约**：每个 item 同时给出 `status`（数据值，中文，向后兼容）与
    `status_key`（稳定英文键，前端据此比较/取样式，不再比较中文文案）。
    `status` 查询参数两种写法都接受（`active` 或 `现行`）。
    """
    try:
        filters: dict[str, str] = {}
        resolved = status_dict.resolve_status_filter(status)
        if resolved:
            filters["status"] = resolved
        keyword = standard_no or name or None
        if keyword:
            filters["keyword"] = keyword

        result = mgr.standard_service.get_list(page=page, size=page_size, filters=filters or None)
        items = [dict(item, status_key=status_dict.status_key(item.get("status"))) for item in result["items"]]
        return {
            "total": result["total"],
            "page": result["page"],
            "page_size": result["size"],
            "items": items,
        }
    except DatabaseError as e:
        logger.error("标准状态列表查询失败: %s", e)
        return JSONResponse({"error": f"数据库查询失败: {e}"}, status_code=500)
    except Exception as e:
        logger.exception("标准状态列表查询异常")
        return JSONResponse({"error": f"查询失败: {e}"}, status_code=500)
