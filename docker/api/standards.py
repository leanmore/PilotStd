# docker/api/standards.py — 标准状态查询 API
# GET  /api/standards/status/stats → 状态统计计数
# GET  /api/standards/status → 分页列表（含筛选）
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standards"])

_VALID_STATUSES = ("现行", "已废止", "未知")


@router.get("/api/standards/status/stats")
def get_status_stats(mgr=Depends(get_manager_dep)):
    """返回各状态的标准计数（现行/已废止/未知）。"""
    try:
        rows = mgr.db.fetchall("SELECT status, COUNT(*) AS cnt FROM standard_validity GROUP BY status")
    except Exception as e:
        logger.exception("查询标准状态统计失败")
        return JSONResponse({"error": f"数据库查询失败: {e}"}, status_code=500)

    result = {"active": 0, "inactive": 0, "unknown": 0}
    for r in rows:
        s = r["status"]
        if s == "现行":
            result["active"] = r["cnt"]
        elif s == "已废止":
            result["inactive"] = r["cnt"]
        elif s == "未知":
            result["unknown"] = r["cnt"]
    return result


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
    where_clauses: list[str] = []
    params: list = []

    if status and status in _VALID_STATUSES:
        where_clauses.append("status = ?")
        params.append(status)
    if standard_no:
        where_clauses.append("standard_number LIKE ?")
        params.append(f"%{standard_no}%")
    if name:
        where_clauses.append("standard_number LIKE ?")
        params.append(f"%{name}%")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    try:
        count_row = mgr.db.fetchone(
            f"SELECT COUNT(*) AS total FROM standard_validity {where_sql}",
            tuple(params),
        )
        total = count_row["total"] if count_row else 0
        offset = (page - 1) * page_size
        rows = mgr.db.fetchall(
            f"SELECT id, standard_number, status, last_checked_at, next_check_at, "
            f"check_count FROM standard_validity {where_sql} "
            "ORDER BY last_checked_at DESC LIMIT ? OFFSET ?",
            tuple(params + [page_size, offset]),
        )
    except Exception as e:
        logger.exception("查询标准状态列表失败")
        return JSONResponse({"error": f"查询失败: {e}"}, status_code=500)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(r) for r in rows],
    }
