# docker/api/pending.py — 待确认标准重新查询 API
from fastapi import Body, Depends
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["pending"])


@router.get("/api/pending")
def get_pending(mgr=Depends(get_manager_dep)):
    """获取所有待确认项（从 pending_lookup 表）。"""
    items = mgr.get_pending_items()
    return {"items": items}


@router.post("/api/pending/requery")
def requery_pending(numbers: list[str] = Body(), site: str = "", mgr=Depends(get_manager_dep)):
    """对待确认标准进行重新查询。指定 site 时置顶该站点，否则引擎自动路由。"""
    results, _ = mgr.query_by_numbers(numbers, preferred_site=site)
    return {
        "results": [
            {
                "standard_number": r.standard_number,
                "standard_name": r.standard_name,
                "status": r.status,
                "source_site": r.source_site,
                "match_status": getattr(r, "match_status", ""),
            }
            for r in results
        ]
    }
