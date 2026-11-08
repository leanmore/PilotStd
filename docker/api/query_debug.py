# 容器//查询_脚本—阶段3.2:路由评分决策链调试接口
"""POST /api/query/debug — 返回完整评分链，支持模拟运行时状态进行 what-if 分析。"""

import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from pilotstd.query.routing.scorer import _collect_runtime_state, score_adapter
from pilotstd.query.site_config import ADAPTER_DEFAULT_PROFILES

from ..auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/query", tags=["debug"])


class DebugRequest(BaseModel):
    """debug 接口请求体：查询词 + 可选的模拟运行时状态。"""

    query: str
    simulate_runtime: Optional[dict[str, dict]] = None


class AdapterScoreResponse(BaseModel):
    """单个适配器的评分结果（debug 接口响应项）。"""

    adapter: str
    score: int
    reasons: list[str]


def _collect_real_runtime_state() -> dict[str, dict]:
    """从当前运行中的 rotator/quota 收集真实运行时状态。

    若 manager 未初始化则返回空字典（debug 接口独立可用）。
    """
    try:
        from pilotstd.manager.facade import get_manager  # type: ignore[attr-defined]

        mgr = get_manager()
        if mgr and hasattr(mgr, "adapter_manager"):
            rotator = mgr.adapter_manager._rotator
            quota = mgr.adapter_manager._quota
            return _collect_runtime_state(rotator, quota)
    except Exception as e:
        # 该端点本身就是排障工具：采集失败却返回空状态，会被误读成「没有运行时状态」。
        logger.warning("debug 端点收集运行时状态失败，返回空状态: %s", e, exc_info=True)
    return {}


@router.post("/debug", response_model=list[AdapterScoreResponse])
@require_role("admin")
def debug_route(request: Request, payload: DebugRequest):
    """返回完整评分链，支持模拟运行时状态进行 what-if 分析。

    仅管理员：该端点暴露全部适配器评分与运行时状态（配额/冷却），
    属内部诊断面，不应开放给普通登录用户。
    """
    runtime = payload.simulate_runtime if payload.simulate_runtime else _collect_real_runtime_state()

    results: list[AdapterScoreResponse] = []
    for adapter_name in ADAPTER_DEFAULT_PROFILES:
        adapter_state = runtime.get(adapter_name, {}) if runtime else {}
        r = score_adapter(adapter_name, payload.query, adapter_state)
        results.append(AdapterScoreResponse(adapter=adapter_name, score=r.score, reasons=r.reasons))

    results.sort(key=lambda x: x.score, reverse=True)
    return results
