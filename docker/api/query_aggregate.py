# 容器//查询脚本—全局聚合搜索端点（P0）
"""全局聚合搜索 API：`POST /api/query/aggregate`。

行为：
- 默认关闭（`query.aggregate.enabled=false`）⇒ 返回 409 + 明确错误，不发任何网络请求；
- 开启后：按路由链选候选站点（受 `max_sites` 限制）并行检索、合并去重、按置信度排序；
- 单站失败/超时不影响整体，响应里逐站给出 `sites[]` 摘要（UI 的「N 个站点暂不可用」数据源）。
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.query.aggregation import AggregationService
from pilotstd.query.routing.router_v2 import RoutingService

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)

# 聚合只读端点说明：不写库、不落盘、不改变任何站点状态；关闭时零网络请求。
router = APIRouter(tags=["query"])

# 能力模型路径：容器内仓库根相对路径（与 `docker/app.py` 同级布局一致）
_CAPABILITIES = Path(__file__).resolve().parents[2] / "config" / "site_capabilities.yaml"


class AggregateItemView(BaseModel):
    """聚合结果条目。"""

    standard_number: str
    standard_name: str = ""
    status: str = ""
    status_key: str = ""
    confidence: str
    sources: list[str]


class AggregateSiteView(BaseModel):
    """单站检索摘要。"""

    site: str
    ok: bool
    elapsed_ms: int
    count: int = 0
    error: str = ""


class AggregateResponse(BaseModel):
    """聚合查询成功响应。"""

    enabled: bool
    query: str
    elapsed_ms: int
    items: list[AggregateItemView]
    sites: list[AggregateSiteView]


def _build_service(mgr) -> AggregationService:
    """按管理器状态构造聚合服务（适配器来自查询引擎；路由来自能力模型）。"""
    engine = getattr(mgr, "query_engine", None)
    site_order: list[str] = []
    if engine is not None and hasattr(engine, "get_all_sites"):
        try:
            site_order = list(engine.get_all_sites() or [])
        except Exception as exc:  # noqa: BLE001 - 站点列表不可用时退回适配器注入
            logger.warning("aggregate site list unavailable: %s", exc)

    def adapter_getter(site: str):
        """取站点适配器（查询引擎可能未初始化/该站未装配，取不到返回 None）。"""
        if engine is None or not hasattr(engine, "get_adapter"):
            return None
        return engine.get_adapter(site)

    routing = None
    try:
        if _CAPABILITIES.exists():
            routing = RoutingService(str(_CAPABILITIES))
    except Exception as exc:  # noqa: BLE001 - 路由不可用时退回注册顺序，聚合仍可用
        logger.warning("aggregate routing init failed, fallback to site order: %s", exc)

    return AggregationService(
        routing=routing,
        config=getattr(mgr, "cfg", None),
        adapter_getter=adapter_getter,
        site_order=site_order,
    )


@router.get("/api/query/aggregate", response_model=AggregateResponse)
def aggregate_query(
    query: str = Query(..., description="standard number or keyword"),
    max_sites: int | None = Query(None, description="override max candidate sites"),
    mgr=Depends(get_manager_dep),
):
    """跨站聚合检索（P0 **纯读**：GET + 不落库；关闭时 409 且零网络请求）。"""
    result = _build_service(mgr).search(query, max_sites=max_sites)
    if not result.enabled:
        return JSONResponse(
            {"error": "aggregate disabled (query.aggregate.enabled=false)"},
            status_code=409,
        )
    return result.to_dict()
