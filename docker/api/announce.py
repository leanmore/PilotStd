# docker/api/announce.py — 标准公告抓取 API（通过 StandardManager 统一入口）
import json
import os
from datetime import datetime

from fastapi import BackgroundTasks, Depends
from fastapi.routing import APIRouter

from ..manager import get_manager as _get_mgr
from ..manager import get_manager_dep

router = APIRouter(tags=["announce"])

# 公告检查结果缓存（供 /api/announce/results 查询）
_cache: dict = {"last_check": "", "results": [], "summary": {}, "failures": []}

FAILURES_FILE = os.path.join(os.environ.get("DATA_DIR", "/app/data"), "announce_failures.json")


def check_announce(since_date: str = "", mgr=None) -> dict:
    """抓取最新公告并更新缓存。通过 StandardManager 统一入口。
    mgr 参数：路由通过 Depends 注入，调度器调用时传 None 走 _get_mgr() 降级。"""
    if mgr is None:
        mgr = _get_mgr()
    result = mgr.check_announcements_filtered(since_date=since_date)
    # 汇总各类型公告明细
    total_matched = 0
    total_updated = 0
    failures = []
    for std_type, r in result.items():
        if isinstance(r, dict):
            total_matched += r.get("matched", 0)
            total_updated += r.get("updated", 0)
            if r.get("error"):
                failures.append({"type": std_type, "error": str(r["error"])})
    # 从 facade 获取公告缓存结果
    items = mgr.get_announcement_cache()
    _cache["results"] = items
    _cache["last_check"] = datetime.now().isoformat()
    _cache["failures"] = failures
    _cache["summary"] = {
        "total_standards": total_matched + total_updated,
        "matched": total_matched,
        "updated": total_updated,
        "new": total_matched,
        "skipped": len(failures),
    }
    # 失败记录持久化到文件，方便人工处理或后续重试
    if failures:
        try:
            os.makedirs(os.path.dirname(FAILURES_FILE), exist_ok=True)
            with open(FAILURES_FILE, "w", encoding="utf-8") as f:
                json.dump(failures, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return {
        "ok": True,
        "count": total_matched + total_updated,
        "failures": len(failures),
    }


@router.post("/api/announce/check")
def api_check_announce(
    since_date: str = "",
    background_tasks: BackgroundTasks = None,
    mgr=Depends(get_manager_dep),
):
    """抓取最新公告（后台异步执行，不阻塞请求线程）。
    since_date 可选，仅抓取该日期之后的公告（格式 YYYY-MM-DD）。"""
    if background_tasks:
        background_tasks.add_task(check_announce, since_date=since_date, mgr=mgr)
        return {"ok": True, "msg": "公告抓取已提交后台执行"}
    return check_announce(since_date=since_date, mgr=mgr)


@router.get("/api/announce/results")
def get_announce_results(from_date: str = "", to_date: str = ""):
    """获取最近一次公告检查的结果缓存。
    可选 from_date/to_date 过滤（格式 YYYY-MM-DD）。"""
    items = _cache.get("results", [])
    if from_date or to_date:
        filtered = []
        for item in items:
            pub = item.get("publish_date", "")
            if from_date and pub < from_date:
                continue
            if to_date and pub > to_date:
                continue
            filtered.append(item)
        return {
            "last_check": _cache.get("last_check", ""),
            "summary": _cache.get("summary", {}),
            "results": filtered,
        }
    return _cache
