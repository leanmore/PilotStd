# docker/api/query.py — 标准有效性查询 API
import json
import os

from fastapi import Body, Depends
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["query"])

# 查询结果持久化文件路径
QUERY_RESULTS_FILE = os.path.join(
    os.environ.get(
        "DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data")
    ),
    "query_results.json",
)


@router.post("/api/query")
def query_standards(
    numbers: list[str] = Body(embed=True),
    force_refresh: bool = False,
    mgr=Depends(get_manager_dep),
):
    """批量查询标准有效性状态。返回完整 17 字段，前端按需取用。"""
    results, stats = mgr.query_by_numbers(numbers, force_refresh=force_refresh)
    return {
        "stats": {
            "total": stats.total,
            "found": stats.found,
            "downloadable": stats.downloadable,
            "not_found": stats.not_found,
        },
        "results": results,
    }


@router.post("/api/query/save")
def save_query_results(results: list[dict] = Body()):
    """保存查询结果到持久化文件，供下载/规范化/待确认页面导入。"""
    os.makedirs(os.path.dirname(QUERY_RESULTS_FILE), exist_ok=True)
    with open(QUERY_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return {"ok": True, "count": len(results)}


@router.get("/api/query/results")
def get_query_results():
    """读取已保存的查询结果。"""
    if not os.path.exists(QUERY_RESULTS_FILE):
        return {"results": []}
    with open(QUERY_RESULTS_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)
    return {"results": results}
