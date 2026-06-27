# docker/api/standards.py — 标准状态查询 API
# GET  /api/standards/status/stats → 状态统计计数
# GET  /api/standards/status → 分页列表（含筛选）
import logging

from fastapi import Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standards"])

_VALID_STATUSES = ("现行", "已废止", "未知")


@router.get("/api/standards/status/stats")
def get_status_stats():
    """返回各状态的标准计数（现行/已废止/未知）。"""
    try:
        db = Database(get_db_path())
        rows = db.fetchall("SELECT status, COUNT(*) AS cnt FROM standard_validity GROUP BY status")
        db.close()
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
):
    """分页查询标准状态列表。name 模糊匹配 standard_number（表中无独立名称字段）。"""
    try:
        db = Database(get_db_path())
    except Exception as e:
        logger.exception("连接数据库失败")
        return JSONResponse({"error": f"数据库连接失败: {e}"}, status_code=500)

    where_clauses: list[str] = []
    params: list = []

    if status and status in _VALID_STATUSES:
        where_clauses.append("status = ?")
        params.append(status)

    if standard_no:
        where_clauses.append("standard_number LIKE ?")
        params.append(f"%{standard_no}%")

    if name:
        # 表中无独立名称字段，用 standard_number 模糊匹配
        where_clauses.append("standard_number LIKE ?")
        params.append(f"%{name}%")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    try:
        # 总数
        count_row = db.fetchone(
            f"SELECT COUNT(*) AS total FROM standard_validity {where_sql}",
            tuple(params),
        )
        total = count_row["total"] if count_row else 0

        # 分页数据
        offset = (page - 1) * page_size
        rows = db.fetchall(
            f"SELECT id, standard_number, status, last_checked_at, next_check_at, "
            f"check_count FROM standard_validity {where_sql} "
            "ORDER BY last_checked_at DESC LIMIT ? OFFSET ?",
            tuple(params + [page_size, offset]),
        )
        db.close()
    except Exception as e:
        logger.exception("查询标准状态列表失败")
        try:
            db.close()
        except Exception:
            pass
        return JSONResponse({"error": f"查询失败: {e}"}, status_code=500)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(r) for r in rows],
    }
