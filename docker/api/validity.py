# docker/api/validity.py — 时效性检查配置与历史 API
# GET  /api/validity/config → 读取时效性检查配置
# PUT  /api/validity/config → 更新时效性检查配置
# POST /api/validity/run → 立即执行一次检查
# GET  /api/validity/history → 获取执行历史
# POST /api/validity/enqueue → 将指定文件加入时效性检查队列
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["validity"])

_DEFAULT_CONFIG = {
    "batch_size": 50,
    "batch_interval": 5,
    "check_ratio": 25,
    "total_weeks": 4,
}


@router.get("/api/validity/config")
def get_validity_config(mgr=Depends(get_manager_dep)):
    """读取时效性检查配置，未设置时返回默认值。"""
    cfg = mgr.cfg
    return {
        "batch_size": cfg.get("validity.batch_size") or _DEFAULT_CONFIG["batch_size"],
        "batch_interval": cfg.get("validity.batch_interval") or _DEFAULT_CONFIG["batch_interval"],
        "check_ratio": cfg.get("validity.check_ratio") or _DEFAULT_CONFIG["check_ratio"],
        "total_weeks": cfg.get("validity.total_weeks") or _DEFAULT_CONFIG["total_weeks"],
        "first_execution": cfg.get("validity.first_execution"),
        "next_run": cfg.get("validity.next_run"),
        "checked_count": cfg.get("validity.checked_count", 0),
        "round_completed": cfg.get("validity.round_completed", False),
        # 已废弃字段（兼容旧前端）
        "frequency": cfg.get("validity.frequency") or "weekly",
        "execute_time": cfg.get("validity.execute_time") or "03:00",
        "update_interval": cfg.get("validity.update_interval") or 28,
    }


@router.put("/api/validity/config")
def update_validity_config(body: dict, mgr=Depends(get_manager_dep)):
    """更新时效性检查配置，校验后写入 ConfigManager。"""
    errors: list[str] = []

    first_execution = body.get("first_execution")
    if first_execution is not None:
        try:
            from datetime import datetime

            datetime.fromisoformat(str(first_execution))
        except (ValueError, TypeError):
            errors.append("first_execution 格式必须为 ISO datetime（如 2026-07-01T03:00:00）")

    total_weeks = body.get("total_weeks")
    if total_weeks is not None and (not isinstance(total_weeks, int) or total_weeks < 4 or total_weeks > 52):
        errors.append("total_weeks 必须为 4-52 之间的整数")

    batch_size = body.get("batch_size")
    if batch_size is not None and (not isinstance(batch_size, int) or batch_size < 1):
        errors.append("batch_size 必须为 >=1 的整数")

    batch_interval = body.get("batch_interval")
    if batch_interval is not None and (not isinstance(batch_interval, int) or batch_interval < 1):
        errors.append("batch_interval 必须为 >=1 的整数")

    check_ratio = body.get("check_ratio")
    if check_ratio is not None and (not isinstance(check_ratio, int) or check_ratio < 1 or check_ratio > 100):
        errors.append("check_ratio 必须为 1-100 之间的整数")

    if errors:
        return JSONResponse({"error": "参数校验失败", "details": errors}, status_code=400)

    field_map = {
        "first_execution": "validity.first_execution",
        "total_weeks": "validity.total_weeks",
        "batch_size": "validity.batch_size",
        "batch_interval": "validity.batch_interval",
        "check_ratio": "validity.check_ratio",
    }
    try:
        for json_key, cfg_key in field_map.items():
            val = body.get(json_key)
            if val is not None:
                mgr.cfg.set(cfg_key, val)
        mgr.cfg.save()
        logger.info("时效性检查配置已更新")
    except Exception as e:
        logger.exception("时效性检查配置写入失败")
        return JSONResponse({"error": f"配置写入失败: {e}"}, status_code=500)

    return {"ok": True, "message": "配置已更新"}


@router.post("/api/validity/run")
def run_validity_check(mgr=Depends(get_manager_dep)):
    """立即触发时效性检查——调用底层 run_validity_check()。"""
    from pilotstd.core.validity_checker import run_validity_check as do_check

    result = do_check(
        notification_mgr=mgr.notification_mgr, db=mgr.db, adapter_mgr=mgr.adapter_manager, update_counters=False
    )
    if result["ok"]:
        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(mgr.db).invalidate_by_source(DataSource.VALIDITY)
        except Exception as e:
            logger.warning("缓存失效失败: %s", e)
        return {"ok": True, "checked": result["checked"], "changed": result["changed"]}
    else:
        return JSONResponse({"error": result.get("error", "执行失败")}, status_code=500)


@router.get("/api/validity/history")
def get_validity_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    mgr=Depends(get_manager_dep),
):
    """获取检查执行历史（按日期聚合 standard_validity 的 last_checked_at）。"""
    return mgr.validity_service.get_history(page, page_size)


@router.post("/api/validity/enqueue")
def enqueue_validity_check(body: dict, mgr=Depends(get_manager_dep)):
    """将指定文件路径加入时效性检查队列。"""
    file_paths: list[str] = body.get("file_paths", []) if isinstance(body.get("file_paths"), list) else []
    if not file_paths:
        return JSONResponse({"error": "file_paths 不能为空"}, status_code=400)
    try:
        result = mgr.validity_service.enqueue_files(file_paths)
        return result
    except Exception as e:
        logger.exception("时效性检查入队失败")
        return JSONResponse({"error": f"入队失败: {e}"}, status_code=500)
