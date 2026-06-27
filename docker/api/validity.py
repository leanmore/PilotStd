# docker/api/validity.py — 时效性检查配置与历史 API
# GET  /api/validity/config → 读取时效性检查配置
# PUT  /api/validity/config → 更新时效性检查配置
# POST /api/validity/run → 立即执行一次检查
# GET  /api/validity/history → 获取执行历史
# POST /api/validity/enqueue → 将指定文件加入时效性检查队列
import logging

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["validity"])

_VALID_FREQUENCIES = ("daily", "weekly", "monthly")
_FREQUENCY_MAP = {"每日": "daily", "每周": "weekly", "每月": "monthly"}

_DEFAULT_CONFIG = {
    "frequency": "weekly",
    "execute_time": "03:00",
    "batch_size": 50,
    "batch_interval": 5,
    "check_ratio": 25,
    "update_interval": 28,
}


@router.get("/api/validity/config")
def get_validity_config(mgr=Depends(get_manager_dep)):
    """读取时效性检查配置，未设置时返回默认值。"""
    cfg = mgr.cfg
    return {
        "frequency": cfg.get("validity.frequency") or _DEFAULT_CONFIG["frequency"],
        "execute_time": cfg.get("validity.execute_time") or _DEFAULT_CONFIG["execute_time"],
        "batch_size": cfg.get("validity.batch_size") or _DEFAULT_CONFIG["batch_size"],
        "batch_interval": cfg.get("validity.batch_interval") or _DEFAULT_CONFIG["batch_interval"],
        "check_ratio": cfg.get("validity.check_ratio") or _DEFAULT_CONFIG["check_ratio"],
        "update_interval": cfg.get("validity.update_interval") or _DEFAULT_CONFIG["update_interval"],
    }


@router.put("/api/validity/config")
def update_validity_config(body: dict, mgr=Depends(get_manager_dep)):
    """更新时效性检查配置，校验后写入 ConfigManager。"""
    errors: list[str] = []

    frequency = body.get("frequency")
    if frequency is not None:
        if frequency not in _VALID_FREQUENCIES:
            errors.append(f"frequency 必须为: {', '.join(_VALID_FREQUENCIES)}")

    execute_time = body.get("execute_time")
    if execute_time is not None:
        parts = str(execute_time).split(":")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            errors.append("execute_time 格式必须为 HH:MM")
        else:
            h, m = int(parts[0]), int(parts[1])
            if h < 0 or h > 23 or m < 0 or m > 59:
                errors.append("execute_time 时间值无效")

    batch_size = body.get("batch_size")
    if batch_size is not None and (not isinstance(batch_size, int) or batch_size < 1):
        errors.append("batch_size 必须为 >=1 的整数")

    batch_interval = body.get("batch_interval")
    if batch_interval is not None and (not isinstance(batch_interval, int) or batch_interval < 1):
        errors.append("batch_interval 必须为 >=1 的整数")

    check_ratio = body.get("check_ratio")
    if check_ratio is not None and (not isinstance(check_ratio, int) or check_ratio < 1 or check_ratio > 100):
        errors.append("check_ratio 必须为 1-100 之间的整数")

    update_interval = body.get("update_interval")
    if update_interval is not None and (not isinstance(update_interval, int) or update_interval < 1):
        errors.append("update_interval 必须为 >=1 的整数")

    if errors:
        return JSONResponse({"error": "参数校验失败", "details": errors}, status_code=400)

    field_map = {
        "frequency": "validity.frequency",
        "execute_time": "validity.execute_time",
        "batch_size": "validity.batch_size",
        "batch_interval": "validity.batch_interval",
        "check_ratio": "validity.check_ratio",
        "update_interval": "validity.update_interval",
    }
    try:
        for json_key, cfg_key in field_map.items():
            val = body.get(json_key)
            if val is not None:
                mgr.cfg.set(cfg_key, val)
        mgr.cfg.save()
        logger.info("时效性检查配置已更新")
    except Exception as e:
        logger.exception("时效性检查配置写入失败")
        return JSONResponse({"error": f"配置写入失败: {e}"}, status_code=500)

    return {"ok": True, "message": "配置已更新"}


@router.post("/api/validity/run")
def run_validity_check(mgr=Depends(get_manager_dep)):
    """立即触发时效性检查——对到期标准执行三级检查。"""
    try:
        checker = mgr.validity_checker
        due = checker.get_due_standards()
        if not due:
            return {"ok": True, "message": "无到期标准需检查", "checked": 0, "changed": 0}

        # 按配置的 batch_size 和 check_ratio 取切片
        batch_size = mgr.cfg.get("validity.batch_size") or _DEFAULT_CONFIG["batch_size"]
        ratio = mgr.cfg.get("validity.check_ratio") or _DEFAULT_CONFIG["check_ratio"]
        # 随机切片
        import random
        import time as _time

        rng = random.Random(int(_time.time()))
        shuffled = list(due)
        rng.shuffle(shuffled)
        sample_size = max(1, int(len(shuffled) * ratio / 100))
        candidates = shuffled[:sample_size]

        changed = 0
        engine = mgr.query_engine if hasattr(mgr, "query_engine") else None
        interval = mgr.cfg.get("validity.batch_interval") or _DEFAULT_CONFIG["batch_interval"]

        for i, std_no in enumerate(candidates):
            try:
                result = checker.check_standard(std_no, query_engine=engine)
                if result:
                    checker.update_status(std_no, result["status"], mgr.notification_mgr)
                    if result.get("previous") and result["previous"] != result["status"]:
                        changed += 1
            except Exception as e:
                logger.warning("检查标准 %s 失败: %s", std_no, e)
            # 批次间隔
            if i > 0 and i % batch_size == 0 and interval > 0:
                _time.sleep(interval)

        logger.info("时效性检查完成: checked=%d changed=%d", len(candidates), changed)
        return {"ok": True, "checked": len(candidates), "changed": changed}
    except Exception as e:
        logger.exception("时效性检查执行失败")
        return JSONResponse({"error": f"执行失败: {e}"}, status_code=500)


@router.get("/api/validity/history")
def get_validity_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """获取检查执行历史（按日期聚合 standard_validity 的 last_checked_at）。"""
    try:
        db = Database(get_db_path())
    except Exception as e:
        logger.exception("连接数据库失败")
        return JSONResponse({"error": f"数据库连接失败: {e}"}, status_code=500)

    try:
        count_row = db.fetchone(
            "SELECT COUNT(DISTINCT DATE(last_checked_at)) AS total "
            "FROM standard_validity WHERE last_checked_at IS NOT NULL"
        )
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        rows = db.fetchall(
            "SELECT DATE(last_checked_at) AS check_date, "
            "COUNT(*) AS checked_count, "
            "SUM(CASE WHEN last_status != status THEN 1 ELSE 0 END) AS changed_count "
            "FROM standard_validity "
            "WHERE last_checked_at IS NOT NULL "
            "GROUP BY DATE(last_checked_at) "
            "ORDER BY check_date DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        )
        db.close()
    except Exception as e:
        logger.exception("查询时效性检查历史失败")
        try:
            db.close()
        except Exception:
            pass
        return JSONResponse({"error": f"查询失败: {e}"}, status_code=500)

    items = [
        {
            "check_date": r["check_date"],
            "checked_count": r["checked_count"],
            "changed_count": r["changed_count"],
            "status": "success",
        }
        for r in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/api/validity/enqueue")
def enqueue_validity_check(body: dict, mgr=Depends(get_manager_dep)):
    """将指定文件路径加入时效性检查队列。"""
    file_paths: list[str] = body.get("file_paths", []) if isinstance(body.get("file_paths"), list) else []
    if not file_paths:
        return JSONResponse({"error": "file_paths 不能为空"}, status_code=400)

    try:
        from pilotstd.core.config import get_db_path as _dbp
        from pilotstd.core.db import Database as _DB

        db = _DB(_dbp())
        inserted = 0
        for fp in file_paths:
            try:
                db.execute(
                    "INSERT OR IGNORE INTO validity_check_queue "
                    "(file_path, status, created_at) VALUES (?, 'pending', datetime('now'))",
                    (str(fp),),
                )
                inserted += 1
            except Exception:
                pass
        db.close()
        logger.info("时效性检查入队: %d/%d", inserted, len(file_paths))
        return {"ok": True, "enqueued": inserted, "total": len(file_paths)}
    except Exception as e:
        logger.exception("时效性检查入队失败")
        return JSONResponse({"error": f"入队失败: {e}"}, status_code=500)
