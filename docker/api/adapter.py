# docker/api/adapter.py — 适配器熔断管理 API（v19）
# GET  /api/adapter/status → 所有适配器状态
# GET  /api/adapter/config → 当前熔断配置
# PUT  /api/adapter/config → 更新熔断配置

import importlib
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
# 公告适配器（非查询类）
_ANNOUNCE_ADAPTERS = {"gb", "hb", "db"}
_MAX_DISPLAY_NAME_LEN = 20


def _get_display_name(adapter_name: str) -> str:
    """从适配器模块读取 DISPLAY_NAME 常量，校验后返回。异常时用适配器名作为 fallback。"""
    try:
        mod = importlib.import_module(f"pilotstd.query.adapters.{adapter_name}")
        dn = getattr(mod, "DISPLAY_NAME", "")
        if isinstance(dn, str) and dn.strip():
            dn = dn.strip()
            if len(dn) > _MAX_DISPLAY_NAME_LEN:
                logger.warning("DISPLAY_NAME 超长 (%d>%d): %s=%r", len(dn), _MAX_DISPLAY_NAME_LEN, adapter_name, dn)
            return dn
    except Exception:
        pass
    logger.debug("无法读取 %s 的 DISPLAY_NAME，使用 fallback", adapter_name)
    return adapter_name


def _get_all_query_adapters() -> list[str]:
    """从 ADAPTER_TYPE_MAP 动态派生全部查询适配器名称（去重）。"""
    from pilotstd.query.search_strategy import ADAPTER_TYPE_MAP

    names: set[str] = set()
    for route in ADAPTER_TYPE_MAP.values():
        if isinstance(route, dict):
            chain = route.get("chain", [])
            if chain:
                names.update(chain)
            primary = route.get("primary", "")
            if primary:
                names.add(primary)
            fallback = route.get("fallback", "")
            if fallback:
                names.add(fallback)
    return sorted(names)


@router.get("/api/adapter/status")
def get_adapter_status(mgr=Depends(get_manager_dep), type: str | None = None):
    """查询适配器的熔断状态。可选 type=announcement 仅公告适配器，type=query 仅查询适配器。"""
    if type == "announcement":
        target_names = sorted(_ANNOUNCE_ADAPTERS)
    elif type == "query":
        target_names = _get_all_query_adapters()
    else:
        target_names = sorted(_ANNOUNCE_ADAPTERS) + _get_all_query_adapters()

    now = datetime.now(timezone.utc)
    adapters = []

    rows = mgr.adapter_manager.get_all_health()
    row_map = {r["adapter_name"]: r for r in rows}

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
                    frozen_until = None
            ft = row["first_freeze_time"]
            first_freeze_time = ft if ft else None

        adapters.append(
            {
                "name": name,
                "display_name": _get_display_name(name) if name not in _ANNOUNCE_ADAPTERS else name,
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
