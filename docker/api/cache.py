# 容器//缓存脚本—缓存管理接口
# //缓存/配置→获取缓存配置
# //缓存/配置→保存缓存配置
# //缓存/→缓存统计
# //缓存/→手动触发清理
import logging

from fastapi import Depends
from fastapi.routing import APIRouter

from pilotstd.core.cache_manager import CacheManager

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cache"])


def _get_cache_mgr(mgr=Depends(get_manager_dep)) -> CacheManager:
    return CacheManager(mgr.db)


@require_role("admin")
@router.get("/api/cache/config")
def get_config(mgr=Depends(get_manager_dep)):
    """获取缓存配置，返回 max_size_mb、auto_cleanup、cleanup_ratio 等参数。"""
    cm = CacheManager(mgr.db)
    return cm.get_config()


@require_role("admin")
@router.put("/api/cache/config")
def put_config(body: dict, mgr=Depends(get_manager_dep)):
    """保存缓存配置，支持更新 max_size_mb、auto_cleanup、cleanup_ratio。

    body 中传入的键会被逐个写入配置，不传的键保持不变。仅管理员可操作。
    """
    cm = CacheManager(mgr.db)
    for key in ("max_size_mb", "auto_cleanup", "cleanup_ratio"):
        if key in body:
            cm.set_config(key, body[key])
    return {"ok": True}


@require_role("admin")
@router.get("/api/cache/stats")
def get_stats(mgr=Depends(get_manager_dep)):
    """获取缓存统计信息，包括当前大小、文件数、命中率等。"""
    cm = CacheManager(mgr.db)
    return cm.get_stats()


@require_role("admin")
@router.post("/api/cache/cleanup")
def trigger_cleanup(mgr=Depends(get_manager_dep)):
    """手动触发缓存清理（强制模式），返回清后统计。仅管理员可操作。"""
    cm = CacheManager(mgr.db)
    cm.cleanup(force=True)
    return {"ok": True, "stats": cm.get_stats()}
