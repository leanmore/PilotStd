# docker/api/adapter.py — 适配器熔断管理 API（v18）
# GET  /api/adapter/status → 所有适配器状态
# GET  /api/adapter/config → 当前熔断配置
# PUT  /api/adapter/config → 更新熔断配置

import logging
from datetime import datetime, timezone

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["adapter"])

_DEFAULT_CONFIG = {
    "failure_threshold": 3,
    "freeze_durations": [30, 120, 360, 720],
    "reset_window_hours": 24,
}
_ALL_ADAPTER_NAMES = [
    # 公告适配器
    "gb",
    "hb",
    "db",
    # 标准查询适配器
    "ahbz",
    "std_gov",
    "hbba",
    "iso_gov",
    "njbz365",
    "csres",
    "dbba",
]


@router.get("/api/adapter/status")
def get_adapter_status(mgr=Depends(get_manager_dep), type: str | None = None):
    """查询适配器的熔断状态。可选 type=announcement 仅公告适配器，type=query 仅查询适配器。"""
    # 按类型过滤
    if type == "announcement":
        target_names = ["gb", "hb", "db"]
    elif type == "query":
        target_names = ["ahbz", "std_gov", "hbba", "iso_gov", "njbz365", "csres", "dbba"]
    else:
        target_names = _ALL_ADAPTER_NAMES

    now = datetime.now(timezone.utc)
    adapters = []

    # 通过 Manager 获取 adapter_health（避免 API 层直接创建 Database）
    try:
        rows = mgr.db.fetchall("SELECT * FROM adapter_health")
        row_map = {r["adapter_name"]: r for r in rows}
    except Exception as e:
        logger.warning("查询 adapter_health 失败: %s", e)
        row_map = {}

    for name in target_names:
        row = row_map.get(name)
        frozen_until = None
        remaining = 0
        status = "normal"
        freeze_count = 0
        first_freeze_time = None
        fail_streak = 0

        if row:
            freeze_count = row["freeze_count"] or 0
            fail_streak = row["fail_streak"] or 0
            fu = row["frozen_until"]
            if fu:
                frozen_until = datetime.fromisoformat(fu)
                if now < frozen_until:
                    status = "frozen"
                    remaining = int((frozen_until - now).total_seconds())
                else:
                    frozen_until = None  # 已过期，展示为 normal
            ft = row["first_freeze_time"]
            first_freeze_time = ft if ft else None

        adapters.append(
            {
                "name": name,
                "status": status,
                "frozen_until": frozen_until.isoformat() if frozen_until else None,
                "remaining_seconds": remaining,
                "freeze_count": freeze_count,
                "first_freeze_time": first_freeze_time,
                "fail_streak": fail_streak,
            }
        )
    return {"adapters": adapters}


@router.get("/api/adapter/config")
def get_adapter_config(mgr=Depends(get_manager_dep)):
    """读取当前熔断配置（含默认值兜底）。"""
    cfg = mgr.cfg
    threshold = cfg.get("adapter.circuit_breaker.failure_threshold")
    durations = cfg.get("adapter.circuit_breaker.freeze_durations")
    reset_hours = cfg.get("adapter.circuit_breaker.reset_window_hours")
    return {
        "failure_threshold": threshold if threshold is not None else _DEFAULT_CONFIG["failure_threshold"],
        "freeze_durations": durations if durations else _DEFAULT_CONFIG["freeze_durations"],
        "reset_window_hours": reset_hours if reset_hours is not None else _DEFAULT_CONFIG["reset_window_hours"],
    }


@router.put("/api/adapter/config")
def update_adapter_config(body: dict, mgr=Depends(get_manager_dep)):
    """更新熔断配置，立即生效（热加载）。"""
    errors = []
    # 校验 failure_threshold
    threshold = body.get("failure_threshold")
    if threshold is not None:
        if not isinstance(threshold, int) or threshold < 1:
            errors.append("failure_threshold 必须为 >=1 的整数")
    # 校验 freeze_durations
    durations = body.get("freeze_durations")
    if durations is not None:
        if not isinstance(durations, list) or len(durations) < 1:
            errors.append("freeze_durations 必须为非空整数列表")
        else:
            for i, d in enumerate(durations):
                if not isinstance(d, int) or d < 1:
                    errors.append(f"freeze_durations[{i}] 必须为 >=1 的整数")
            # 检查递增
            for i in range(1, len(durations)):
                if isinstance(durations[i], int) and isinstance(durations[i - 1], int):
                    if durations[i] <= durations[i - 1]:
                        errors.append("freeze_durations 必须严格递增")
                        break
    # 校验 reset_window_hours
    reset_hours = body.get("reset_window_hours")
    if reset_hours is not None:
        if not isinstance(reset_hours, int) or reset_hours < 1:
            errors.append("reset_window_hours 必须为 >=1 的整数")
    if errors:
        return JSONResponse({"error": "参数校验失败", "details": errors}, 400)

    # 写入配置
    try:
        if threshold is not None:
            mgr.cfg.set("adapter.circuit_breaker.failure_threshold", threshold)
        if durations is not None:
            mgr.cfg.set("adapter.circuit_breaker.freeze_durations", durations)
        if reset_hours is not None:
            mgr.cfg.set("adapter.circuit_breaker.reset_window_hours", reset_hours)
        mgr.cfg.save()
        logger.info("熔断配置已更新: threshold=%s durations=%s window=%sh", threshold, durations, reset_hours)
    except Exception as e:
        logger.exception("熔断配置写入失败")
        return JSONResponse({"error": f"配置写入失败: {e}"}, 500)

    # 返回更新后的完整配置
    return {
        "message": "配置已更新",
        "config": get_adapter_config(mgr=mgr),
    }


@router.post("/api/adapter/test")
def test_adapter(name: str, mgr=Depends(get_manager_dep)):
    """测试单个适配器的连通性。"""
    if not hasattr(mgr, "adapter_manager"):
        return JSONResponse({"ok": False, "message": "适配器管理器未初始化"}, status_code=503)
    result = mgr.adapter_manager.test_adapter(name)
    return result
