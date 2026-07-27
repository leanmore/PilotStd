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
from pydantic import BaseModel, Field, validator

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["validity"])

_DEFAULT_CONFIG = {
    "batch_size": 50,
    "batch_interval": 5,
    "check_ratio": 25,
    "total_weeks": 4,
    "frequency_weeks": 1,
    "first_weekday": 1,
    "execute_time": "03:00",
}


# ✅ #43: Pydantic 校验模型
class ValidityConfigUpdate(BaseModel):
    """时效性检查配置更新请求体，含前后端双重校验"""

    first_weekday: int = Field(..., ge=1, le=7, description="首次执行周几（1=周一, 7=周日）")
    execute_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="执行时间（HH:MM）")
    total_weeks: int = Field(..., ge=4, description="总周期（周），≥4")
    frequency_weeks: int = Field(..., ge=1, description="执行频率（周），≥1")

    @validator("frequency_weeks")
    def frequency_weeks_le_total(cls, v, values):
        """校验执行频率不超过总周期"""
        total = values.get("total_weeks")
        if total and v > total:
            raise ValueError("执行频率不能超过总周期")
        return v


@router.get("/api/validity/config")
def get_validity_config(mgr=Depends(get_manager_dep)):
    """读取时效性检查配置，未设置时返回默认值。"""
    cfg = mgr.cfg
    return {
        "batch_size": cfg.get("validity.batch_size") or _DEFAULT_CONFIG["batch_size"],
        "batch_interval": cfg.get("validity.batch_interval") or _DEFAULT_CONFIG["batch_interval"],
        "check_ratio": cfg.get("validity.check_ratio") or _DEFAULT_CONFIG["check_ratio"],
        "total_weeks": cfg.get("validity.total_weeks") or _DEFAULT_CONFIG["total_weeks"],
        # ✅ #43: 新增字段
        "frequency_weeks": cfg.get("validity.frequency_weeks") or _DEFAULT_CONFIG["frequency_weeks"],
        "first_weekday": cfg.get("validity.first_weekday") or _DEFAULT_CONFIG["first_weekday"],
        "execute_time": cfg.get("validity.execute_time") or _DEFAULT_CONFIG["execute_time"],
        "first_execution": cfg.get("validity.first_execution"),
        "next_run": cfg.get("validity.next_run"),
        "checked_count": cfg.get("validity.checked_count", 0),
        "round_completed": cfg.get("validity.round_completed", False),
        # 已废弃字段（兼容旧前端）
        "frequency": cfg.get("validity.frequency") or "weekly",
        "update_interval": (cfg.get("validity.total_weeks") or _DEFAULT_CONFIG["total_weeks"]) * 7,
    }


@router.put("/api/validity/config")
def update_validity_config(body: dict, mgr=Depends(get_manager_dep)):
    """更新时效性检查配置。

    ✅ #43: 保存后立即调用 reschedule_validity_job() 更新 CronTrigger。
    调度器实例与 scheduler_service 为同一全局单例。
    """
    errors: list[str] = []

    first_weekday = body.get("first_weekday")
    if first_weekday is not None:
        if not isinstance(first_weekday, int) or first_weekday < 1 or first_weekday > 7:
            errors.append("first_weekday 必须为 1-7 之间的整数")

    execute_time = body.get("execute_time")
    if execute_time is not None:
        import re

        if not isinstance(execute_time, str) or not re.match(r"^\d{2}:\d{2}$", execute_time):
            errors.append("execute_time 格式必须为 HH:MM")

    total_weeks = body.get("total_weeks")
    # 兼容旧前端：如果发的是 update_interval（天数），转换为 total_weeks（周数）
    if total_weeks is None:
        raw_interval = body.get("update_interval")
        if raw_interval is not None and isinstance(raw_interval, (int, float)):
            total_weeks = max(1, int(raw_interval) // 7)
    if total_weeks is not None and (not isinstance(total_weeks, int) or total_weeks < 4 or total_weeks > 52):
        errors.append("total_weeks 必须为 4-52 之间的整数")

    frequency_weeks = body.get("frequency_weeks")
    if frequency_weeks is not None:
        if not isinstance(frequency_weeks, int) or frequency_weeks < 1:
            errors.append("frequency_weeks 必须为 ≥1 的整数")
        elif total_weeks and frequency_weeks > total_weeks:
            errors.append("frequency_weeks 不能超过 total_weeks")

    # ✅ #43: execution_count 校验（前后端双重拒绝）
    if total_weeks and frequency_weeks:
        exec_count = total_weeks / frequency_weeks
        if exec_count < 4:
            errors.append(f"执行次数为 {exec_count:.1f} 次，需 >= 4 次，请调整总周期或执行频率")

    first_execution = body.get("first_execution")
    if first_execution is not None:
        try:
            from datetime import datetime

            datetime.fromisoformat(str(first_execution))
        except (ValueError, TypeError):
            errors.append("first_execution 格式必须为 ISO datetime（如 2026-07-01T03:00:00）")

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
        "frequency_weeks": "validity.frequency_weeks",
        "first_weekday": "validity.first_weekday",
        "execute_time": "validity.execute_time",
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
        logger.info("时效性检查配置已保存")
    except Exception as e:
        logger.exception("时效性检查配置写入失败")
        return JSONResponse({"error": f"配置写入失败: {e}"}, status_code=500)

    # ✅ #43: 配置保存后立即更新调度器 CronTrigger
    # 注意：必须在 mgr.cfg.save() 之后、HTTP 响应返回之前调用
    try:
        from docker.scheduler import reschedule_validity_job

        reschedule_validity_job()
        logger.info("时效性检查调度已更新")
    except Exception:
        logger.exception("调度器更新失败，配置已保存但调度未生效")
        # 调度失败不阻断配置保存，仅记录日志

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
