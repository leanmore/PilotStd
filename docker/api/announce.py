# docker/api/announce.py — 标准公告抓取 API（通过 StandardManager 统一入口）
import json
import logging
import os
from datetime import datetime

from fastapi import BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager as _get_mgr
from ..manager import get_manager_dep

router = APIRouter(tags=["announce"])
logger = logging.getLogger(__name__)

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
    items = mgr.get_announcement_match()
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
    # 公告抓取完成后标记缓存失效
    try:
        from pilotstd.core.cache_manager import CacheManager, DataSource

        CacheManager(mgr.db).invalidate_by_source(DataSource.ANNOUNCEMENT)
    except Exception as e:
        logger.warning("公告缓存失效失败: %s", e)

    count = total_matched + total_updated
    failure_count = len(failures)
    if mgr and mgr.notification_mgr:
        try:
            mgr.notification_mgr.send_event(
                "announcement_check_complete",
                {
                    "count": count,
                    "failures": failure_count,
                },
            )
        except Exception as e:
            logger.warning("通知发送失败: %s", e)

    return {
        "ok": True,
        "count": count,
        "failures": failure_count,
    }


def _sync_wait_check(since_date: str = "", mgr=None, timeout: int = 60) -> dict:
    """sync=true 兼容模式：通过 AnnounceService 创建异步任务后同步等待。"""
    import time as _time

    # 委托 AnnounceService 创建抓取任务
    result = mgr.announce_service.trigger_fetch()
    task_id = result["task_id"]

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        status = mgr.announce_service.get_task_status(task_id)
        st = status.get("status", "")
        if st == "success":
            data = mgr.announce_service.get_task_results(task_id)
            return data.get("data", {})
        if st == "failed":
            return {"ok": False, "count": 0, "failures": 1, "error": status.get("error_msg", "")}
        if "error" in status:
            return {"ok": False, "count": 0, "failures": 1, "error": "任务丢失"}
        _time.sleep(1)

    return JSONResponse(
        {"code": 408, "msg": "同步等待超时，请改用异步模式 POST /api/announcements/fetch", "task_id": task_id},
        408,
    )


@router.post("/api/announce/check")
def api_check_announce(
    since_date: str = "",
    sync: bool = False,
    background_tasks: BackgroundTasks = None,
    mgr=Depends(get_manager_dep),
):
    """抓取最新公告。
    - sync=False（默认）：后台异步执行，不阻塞请求线程，返回 msg
    - sync=True：同步执行，返回实际抓取的 count 和 failures 数
    since_date 可选，仅抓取该日期之后的公告（格式 YYYY-MM-DD）。
    """
    if sync:
        logger.warning("[DEPRECATED] sync=true 调用已弃用，请迁移至 POST /api/announcements/fetch 异步模式")
        return _sync_wait_check(since_date=since_date, mgr=mgr)
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


@router.get("/api/announce/fetch-log")
def get_announcement_records(limit: int = 100, mgr=Depends(get_manager_dep)):
    """查询公告抓取记录（全量，含未匹配），供压测样本生成。"""
    items = mgr.announce_service.get_announcement_sources(limit=limit)
    return {"total": len(items), "items": items}
