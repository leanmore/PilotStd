# 容器//脚本—标准公告抓取接口（通过统一入口）
import json
import logging
import os
from datetime import datetime
from typing import Any, cast

from fastapi import BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.constants.announce_types import SOURCE_SITE_TO_TYPE

from ..manager import get_manager as _get_mgr
from ..manager import get_manager_dep

router = APIRouter(tags=["announce"])
logger = logging.getLogger(__name__)

FAILURES_FILE = os.path.join(os.environ.get("DATA_DIR", "/app/data"), "announce_failures.json")


def check_announce(since_date: str = "", mgr=None, types: list[str] | None = None) -> dict:
    """抓取最新公告。通过 StandardManager 统一入口。
    mgr 参数：路由通过 Depends 注入，调度器调用时传 None 走 _get_mgr() 降级。
    types 参数：限定抓取的公告类型列表，如 ['gb', 'hb']，None 表示全部。"""
    if mgr is None:
        mgr = _get_mgr()
    check_start = datetime.now().isoformat()
    result = mgr.check_announcements_filtered(since_date=since_date, types=types)
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
    # 失败记录持久化到文件，方便人工处理或后续重试
    if failures:
        try:
            os.makedirs(os.path.dirname(FAILURES_FILE), exist_ok=True)
            with open(FAILURES_FILE, "w", encoding="utf-8") as f:
                json.dump(failures, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    # 公告抓取完成后标记缓存失效（查询缓存 + 统计缓存）
    try:
        from pilotstd.core.cache_manager import CacheManager, DataSource

        CacheManager(mgr.db).invalidate_by_source(DataSource.ANNOUNCEMENT)
    except Exception as e:
        logger.warning("公告缓存失效失败: %s", e)
    # 刷新统计缓存，确保前端立即看到最新数据
    _stats_cache["data"] = None
    _stats_cache["ts"] = 0

    count = total_matched + total_updated
    failure_count = len(failures)
    if mgr and mgr.notification_mgr:
        try:
            # 从_表查询本次新增公告的分类统计
            stats = _get_check_stats(mgr.db, check_start)
            stats["failures"] = failure_count
            stats["source"] = "手动"
            mgr.notification_mgr.send_event("announcement_check_complete", stats)
            # 手动路径：拉取完成极简反馈（仅手动路径触发，定时路径不发此事件）
            # 附本次新增公告标题明细（抓取时间窗口精确匹配本次检查起点之后）
            ann_rows = mgr.db.fetchall(
                "SELECT announce_no, announcement_title FROM announcement_record "
                "WHERE fetched_at >= ? AND announcement_title IS NOT NULL AND announcement_title != '' "
                "GROUP BY announce_no ORDER BY announce_no LIMIT 20",
                (check_start,),
            )
            announcements = [
                {"announce_no": r["announce_no"], "title": r["announcement_title"]} for r in ann_rows
            ]
            mgr.notification_mgr.send_event(
                "announcement_fetch_complete",
                {
                    "count": stats["total_announcements"],
                    "source": stats["source"],
                    "gb_count": stats["gb_count"],
                    "hb_count": stats["hb_count"],
                    "db_count": stats["db_count"],
                    "announcements": announcements,
                },
            )
        except Exception as e:
            logger.warning("通知发送失败: %s", e)

    return {
        "ok": True,
        "count": count,
        "failures": failure_count,
    }


def check_announce_scheduled(mgr=None) -> dict:
    """定时自动抓取公告（从 fetch_checkpoint 增量抓取，不复用 check_announce）。
    与 check_announce 的关键区别：since_date 来自 fetch_checkpoint 表，
    而非用户输入。避免每次定时任务都拉取全量历史数据。"""
    if mgr is None:
        mgr = _get_mgr()
    result: dict = mgr._announce_svc.check_announce_scheduled()
    return result


def _sync_wait_check(since_date: str = "", mgr=None, types: list[str] | None = None, timeout: int = 60) -> dict:
    """sync=true 兼容模式：通过 AnnounceService 创建异步任务后同步等待。"""
    import time as _time

    # 委托创建抓取任务
    result = mgr._announce_svc.trigger_fetch()
    task_id = result["task_id"]

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        status = mgr._announce_svc.get_task_status(task_id)
        st = status.get("status", "")
        if st == "success":
            data = mgr._announce_svc.get_task_results(task_id)
            return cast("dict[Any, Any]", data.get("data", {}))
        if st == "failed":
            return {"ok": False, "count": 0, "failures": 1, "error": status.get("error_msg", "")}
        if "error" in status:
            return {"ok": False, "count": 0, "failures": 1, "error": "任务丢失"}
        _time.sleep(1)

    return JSONResponse(  # type: ignore[return-value, no-any-return]
        {"code": 408, "msg": "同步等待超时，请改用异步模式 POST /api/announcements/fetch", "task_id": task_id},
        408,
    )


@router.post("/api/announce/check")
def api_check_announce(
    since_date: str = "",
    sync: bool = False,
    types: str = "",
    background_tasks: BackgroundTasks = None,  # type: ignore[assignment]
    mgr=Depends(get_manager_dep),
):
    """抓取最新公告。
    - sync=False（默认）：后台异步执行，不阻塞请求线程，返回 msg
    - sync=True：同步执行，返回实际抓取的 count 和 failures 数
    since_date 可选，仅抓取该日期之后的公告（格式 YYYY-MM-DD）。
    types 可选，逗号分隔的公告类型（gb,hb,db），不传则抓取全部。
    """
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    if sync:
        logger.warning("[DEPRECATED] sync=true 调用已弃用，请迁移至 POST /api/announcements/fetch 异步模式")
        return _sync_wait_check(since_date=since_date, mgr=mgr, types=type_list)
    if background_tasks:
        background_tasks.add_task(check_announce, since_date=since_date, mgr=mgr, types=type_list)
        return {"ok": True, "msg": "公告抓取已提交后台执行"}
    return check_announce(since_date=since_date, mgr=mgr, types=type_list)


@router.get("/api/announce/results")
def get_announce_results(
    source_site: str = "",
    from_date: str = "",
    to_date: str = "",
    mgr=Depends(get_manager_dep),
):
    """获取最新公告列表。ROW_NUMBER 窗口去重——同公告号优先保留有日期、最近抓取的行。"""
    db = mgr.db
    inner = (
        "SELECT announce_no, announcement_title, standard_count,"
        " publish_date, fetched_at, source_site,"
        " ROW_NUMBER() OVER ("
        "   PARTITION BY announce_no"
        "   ORDER BY"
        "     CASE WHEN publish_date IS NOT NULL AND publish_date != '' THEN 0 ELSE 1 END,"
        "     fetched_at DESC"
        " ) AS rn"
        " FROM announcement_record"
        " WHERE announce_no IS NOT NULL AND announce_no != ''"
    )
    params: list = []

    if source_site:
        inner += " AND source_site = ?"
        params.append(source_site)
    if from_date:
        inner += " AND date(publish_date) >= ?"
        params.append(from_date)
    if to_date:
        inner += " AND date(publish_date) <= ?"
        params.append(to_date)

    try:
        query = (
            f"SELECT announce_no, announcement_title, standard_count,"
            f" publish_date, fetched_at, source_site"
            f" FROM ({inner}) WHERE rn = 1"
            " ORDER BY"
            " CAST(substr(announce_no, 1, 4) AS INTEGER) DESC,"
            " CAST(substr(announce_no, instr(announce_no, '第')+1,"
            " instr(announce_no, '号')-instr(announce_no, '第')-1) AS INTEGER) DESC,"
            " publish_date DESC LIMIT 100"
        )
    except Exception:
        logger.warning("排序逻辑异常（可能 announce_no 格式异常），降级为按抓取时间排序")
        query = (
            f"SELECT announce_no, announcement_title, standard_count,"
            f" publish_date, fetched_at, source_site"
            f" FROM ({inner}) WHERE rn = 1"
            " ORDER BY fetched_at DESC LIMIT 100"
        )

    rows = db.fetchall(query, params)

    results = []
    for row in rows:
        results.append(
            {
                "announce_no": row["announce_no"],
                "announcement_title": row["announcement_title"] or "",
                "standard_count": row["standard_count"],
                "publish_date": row["publish_date"] or "",
                "source_site": row["source_site"],
                # ✅#47:新增_字段，前端三栏分组使用
                "standard_type": SOURCE_SITE_TO_TYPE.get(row.get("source_site", ""), "other"),
            }
        )

    return {"results": results}


@router.get("/api/announce/fetch-log")
def get_announcement_records(limit: int = 100, mgr=Depends(get_manager_dep)):
    """查询公告抓取记录（全量，含未匹配），供压测样本生成。"""
    items = mgr._announce_svc.get_announcement_sources(limit=limit)
    return {"total": len(items), "items": items}


# 统计缓存（避免频繁扫全表）
_stats_cache: dict = {"data": None, "ts": 0}
_STATS_CACHE_TTL = 300  # 5 分钟


@router.get("/api/announce/stats")
def get_announce_stats(mgr=Depends(get_manager_dep)):
    """公告统计数据（标准总数/已匹配/今日新增，按国标/行标/地标分类）。5分钟缓存。

    ⚠️ 统计口径说明：
    - 标准总数 = announcement_record 表的记录行数（COUNT(*)），每条记录对应
      一个 (公告, 标准号) 组合。同一标准号出现在不同公告中会分别计数。
    - 已匹配 = announcement_record 中 matched=1 的行数。
    - 今日新增 = 今天抓取入库的行数。
    - 严禁使用 SUM(standard_count) 做统计：_normalize() 会将同公告的所有行
      写入相同的条目总数，SUM 会导致 N² 膨胀。
    """
    import time

    now_ts = time.time()
    if _stats_cache["data"] and (now_ts - _stats_cache["ts"]) < _STATS_CACHE_TTL:
        return _stats_cache["data"]

    db = mgr.db

    # 首次调用时记录服务器时间，只执行一次
    if not hasattr(get_announce_stats, "_tz_checked"):
        from datetime import datetime

        logger.info("当前服务器时间: %s", datetime.now().isoformat())
        get_announce_stats._tz_checked = True  # type: ignore[attr-defined]

    today = "date('now', 'localtime')"

    # 全量统计：计数(*)统计行数，每条(公告,标准号)计1
    all_row = db.fetchone(
        "SELECT COUNT(*) as total,"
        " SUM(CASE WHEN source_site='announcement_gb' THEN 1 ELSE 0 END) as gb,"
        " SUM(CASE WHEN source_site='announcement_hb' THEN 1 ELSE 0 END) as hb,"
        " SUM(CASE WHEN source_site='announcement_db' THEN 1 ELSE 0 END) as db"
        " FROM announcement_record"
    )
    # 今日抓取
    today_row = db.fetchone(
        "SELECT COUNT(*) as total,"
        " SUM(CASE WHEN source_site='announcement_gb' THEN 1 ELSE 0 END) as gb,"
        " SUM(CASE WHEN source_site='announcement_hb' THEN 1 ELSE 0 END) as hb,"
        " SUM(CASE WHEN source_site='announcement_db' THEN 1 ELSE 0 END) as db"
        f" FROM announcement_record WHERE date(fetched_at)={today}"
    )
    # 已匹配
    matched_row = db.fetchone("SELECT COUNT(*) as cnt FROM announcement_record WHERE matched=1")

    def _val(row, key, default=0):
        if not row:
            return default
        v = row[key]
        return v if v is not None else default

    all_gb = _val(all_row, "gb")
    all_hb = _val(all_row, "hb")
    all_db = _val(all_row, "db")
    today_gb = _val(today_row, "gb")
    today_hb = _val(today_row, "hb")
    today_db = _val(today_row, "db")

    result = {
        "total": {
            "all": all_gb + all_hb + all_db,
            "gb": all_gb,
            "hb": all_hb,
            "db": all_db,
        },
        "matched": _val(matched_row, "cnt"),
        "new": {
            "all": _val(today_row, "total"),
            "gb": today_gb,
            "hb": today_hb,
            "db": today_db,
        },
    }
    _stats_cache["data"] = result
    _stats_cache["ts"] = now_ts
    return result


def _get_check_stats(db: Any, since: str) -> dict[str, Any]:
    """从 announcement_record 表查询 since 之后新增公告的分类统计。
    - 公告数 = COUNT(DISTINCT announce_no)（一个公告号对应多条标准记录）
    - 标准数 = COUNT(*)（每条记录代表一项标准）
    - 严禁使用 SUM(standard_count)，standard_count 是公告内条目数，
      同一公告的多条记录共享此值，SUM 会产生 N² 膨胀。"""
    rows = db.fetchall(
        "SELECT source_site,"
        " COUNT(DISTINCT announce_no) AS ann_cnt, COUNT(*) AS std_cnt "
        "FROM announcement_record WHERE fetched_at >= ? GROUP BY source_site",
        (since,),
    )
    stats: dict[str, Any] = {
        "total_announcements": 0,
        "total_standards": 0,
        "gb_count": 0,
        "hb_count": 0,
        "db_count": 0,
        "gb_standards": 0,
        "hb_standards": 0,
        "db_standards": 0,
    }
    for r in rows:
        ann_cnt = r["ann_cnt"] or 0
        std_cnt = r["std_cnt"] or 0
        source = r["source_site"]
        if source == "announcement_gb":
            stats["gb_count"] = ann_cnt
            stats["gb_standards"] = std_cnt
        elif source == "announcement_hb":
            stats["hb_count"] = ann_cnt
            stats["hb_standards"] = std_cnt
        elif source == "announcement_db":
            stats["db_count"] = ann_cnt
            stats["db_standards"] = std_cnt
        stats["total_announcements"] += ann_cnt
        stats["total_standards"] += std_cnt
    return stats
