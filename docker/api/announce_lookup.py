# 容器//_脚本—公告缓存精确查询接口
from fastapi import Depends, Query
from fastapi.routing import APIRouter
from pydantic import BaseModel

from ..manager import get_manager_dep

router = APIRouter(tags=["announce"])

# ════════════════════════════════════════════════════════════════ 分隔
# 响应模型：与路由成功返回的字典键一一对应（命中与未命中字段互斥）
# ════════════════════════════════════════════════════════════════ 分隔


class AnnounceLookupDataItem(BaseModel):
    """公告缓存查询摘要：标准名称与抓取时间。"""

    standard_name: str | None = None
    fetched_at: str


class AnnounceLookupResponse(BaseModel):
    """按标准号查询公告缓存的结果：命中标记、摘要数据与未命中提示。"""

    found: bool
    data: AnnounceLookupDataItem | None = None
    message: str | None = None
    cached_at: str | None = None
    source: str | None = None


@router.get(
    "/api/announce/lookup",
    response_model=AnnounceLookupResponse,
    response_model_exclude_none=True,
)
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
