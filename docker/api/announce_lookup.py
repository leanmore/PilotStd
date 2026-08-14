# 容器//_脚本—公告缓存精确查询接口
from fastapi import Depends, Query
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["announce"])


@router.get("/api/announce/lookup")
def lookup_announcement(
    number: str = Query(..., description="标准号，精确匹配"),
    mgr=Depends(get_manager_dep),
):
    """按标准号精确查询公告抓取记录，返回匹配结果。"""
    row = mgr._announce_svc.lookup_announcement(number)

    if row is None:
        return {
            "found": False,
            "data": None,
            "message": "未在公告抓取记录中找到该标准",
        }

    return {
        "found": True,
        "data": {"standard_name": row["std_name"], "fetched_at": row["fetched_at"]},
        "cached_at": row["fetched_at"],
        "source": "announcement_record",
    }
