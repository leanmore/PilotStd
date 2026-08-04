# 容器//脚本—统计口径接口
from fastapi import Depends
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["stats"])


@router.get("/api/stats")
def get_stats(mgr=Depends(get_manager_dep)):
    """返回标准库统计：现行/废止/待确认/即将实施数量。"""
    return mgr.file_index.get_status_stats()
