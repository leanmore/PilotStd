# docker/api/announce_lookup.py — 公告缓存精确查询 API
import json
import logging

from fastapi import Depends, HTTPException, Query
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["announce"])


@router.get("/api/announce/lookup")
def lookup_announcement(
    number: str = Query(..., description="标准号，精确匹配"),
    mgr=Depends(get_manager_dep),
):
    """按标准号精确查询公告抓取记录，返回匹配结果。"""
    try:
        rows = mgr.db.fetchall(
            "SELECT standard_number, source_site, std_name, fetched_at "
            "FROM announcement_record WHERE standard_number = ? "
            "ORDER BY fetched_at DESC LIMIT 1",
            (number,),
        )
    except Exception as e:
        logger.error("公告抓取记录查询失败 标准号=%s: %s", number, e)
        raise HTTPException(status_code=500, detail=f"数据库查询失败: {e}")

    if not rows:
        return {
            "found": False,
            "data": None,
            "message": "未在公告抓取记录中找到该标准",
        }

    row = rows[0]
    try:
        result_data = {"standard_name": row[2], "fetched_at": row[3]}
    except (json.JSONDecodeError, TypeError):
        result_data = row[2]

    return {
        "found": True,
        "data": result_data,
        "cached_at": row[3],
        "source": "announcement_record",
    }
