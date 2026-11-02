# 容器//脚本—统计口径接口
from fastapi import Depends
from fastapi.routing import APIRouter
from pydantic import BaseModel

from ..manager import get_manager_dep

router = APIRouter(tags=["stats"])


class StatusStatsResponse(BaseModel):
    """标准库状态统计响应：现行、废止、待确认与即将实施数量。"""

    current: int
    expired: int
    pending: int
    upcoming: int


@router.get("/api/stats", response_model=StatusStatsResponse)
def get_stats(mgr=Depends(get_manager_dep)):
    """返回标准库统计：现行/废止/待确认/即将实施数量。"""
    return mgr.file_index.get_status_stats()
