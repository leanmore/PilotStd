"""适配器健康检查 API（只读最近结果 + 手动触发）。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from pilotstd.query.health_probe import get_last_result, run_health_check

from ..auth import require_role

router = APIRouter(tags=["adapter-health"])


class AdapterHealthResponse(BaseModel):
    """最近一次适配器健康检查结果。"""

    checked_at: str = ""
    summary: dict[str, int] = {}
    results: list[dict] = []


@router.get("/api/adapters/health", response_model=AdapterHealthResponse)
@require_role("admin")
def get_adapter_health(request: Request):
    """返回最近一次结果；从未跑过时为空结构。"""
    last = get_last_result()
    if not last:
        return {"checked_at": "", "summary": {}, "results": []}
    return last


@router.post("/api/adapters/health/run", response_model=AdapterHealthResponse)
@require_role("admin")
def run_adapter_health(request: Request):
    """手动触发一轮（21 请求，约 1 分钟内），供首轮样本与排障。"""
    return run_health_check()
