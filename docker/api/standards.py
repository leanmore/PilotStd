# 容器//脚本—标准状态查询接口
# ////→状态统计计数
# ///→分页列表（含筛选）
import logging

from fastapi import Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core import status as status_dict
from pilotstd.core.db._constants import DatabaseError
from pilotstd.core.status import Status

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standards"])


class StandardStatusStatsResponse(BaseModel):
    """标准状态计数响应：现行、已废止、未知三类。"""

    active: int
    inactive: int
    unknown: int


class StandardStatusItem(BaseModel):
    """单个标准的状态条目：数据值 status（中文）与稳定英文键 status_key 并存。"""

    id: int
    standard_number: str
    status: str
    std_name: str
    last_checked_at: str | None
    check_count: int
    status_key: str


class StandardStatusListResponse(BaseModel):
    """标准状态分页列表响应。"""

    total: int
    page: int
    page_size: int
    items: list[StandardStatusItem]


@router.get("/api/standards/status/stats", response_model=StandardStatusStatsResponse)
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


@router.get("/api/standards/status", response_model=StandardStatusListResponse)
def get_standards_status(
    status: str | None = Query(
        None,
        description=(
            "英文键（active/upcoming/withdrawn/unknown 等）或历史中文值"
            "（现行/即将实施/废止/未知 等）；历史别名 未生效=即将实施"
        ),
    ),
    standard_no: str | None = Query(None),
    name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mgr=Depends(get_manager_dep),
):
    """分页查询标准状态列表。

    **响应契约**：每个 item 同时给出 `status`（数据值，中文，向后兼容）与
    `status_key`（稳定英文键，前端据此比较/取样式，不再比较中文文案）。

    **过滤契约**（与 `pilotstd.core.status.API_FILTER_ACCEPTED_VALUES` 同源，单一事实源）：
    `status` 查询参数接受三类写法：
    - 英文契约键：`active` / `upcoming` / `withdrawn` / `superseded` / `voided` /
      `expired` / `pending` / `unknown`；
    - 历史中文值：`现行` / `即将实施` / `废止` / `已废止` / `被代替` / `作废` /
      `过期` / `待确认` / `未知`（旧前端 / 老书签）；
    - 历史兼容别名：`未生效`（= `即将实施`，C3 存量清洗后自然收敛）。

    **无法识别的非空取值显式返回 400**，不再静默忽略过滤条件（P1-5 §5.1 的 P0 缺陷：
    旧实现下 `?status=未生效` 会返回全表）；空值 / 纯空白 = 「不筛选」。
    """
    raw_status = (status or "").strip()
    if raw_status and not status_dict.is_valid_status_filter(raw_status):
        # P0 防复发核心：过滤值非法必须显式失败，而不是静默退化成「全表」
        raise HTTPException(
            status_code=400,
            detail=f"无法识别的状态过滤值: {status}",  # i18n-allow: API 错误文案（同文件既有风格）
        )
    try:
        filters: dict[str, str] = {}
        resolved = status_dict.resolve_status_filter(raw_status or None)
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
