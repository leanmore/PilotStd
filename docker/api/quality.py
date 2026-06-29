# docker/api/quality.py — 数据质量检查 API
import logging

from fastapi import Depends
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quality"])


@router.post("/api/quality/run")
def run_quality_check(mgr=Depends(get_manager_dep)):
    """运行数据质量检查。"""
    return mgr.quality_service.run_check()
