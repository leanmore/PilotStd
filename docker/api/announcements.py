# docker/api/announcements.py — 公告抓取异步 API（v18）
# POST /api/announcements/fetch → 触发后台抓取
# GET  /api/announcements/status/{task_id} → 查询进度
# GET  /api/announcements/results/{task_id} → 获取结果

import json
import logging
import threading
import uuid
from datetime import datetime, timezone

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep
from .announce import check_announce

logger = logging.getLogger(__name__)
router = APIRouter(tags=["announcements"])


def _run_fetch_task(task_id: str, adapter_name: str, mgr) -> None:
    """后台线程：执行公告抓取，更新 fetch_task 状态。"""
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    db = Database(get_db_path())
    now = datetime.now(timezone.utc).isoformat()
    try:
        # 更新为 running
        db.execute(
            "UPDATE fetch_task SET status='running', progress=10, updated_at=? WHERE id=?",
            (now, task_id),
        )
        logger.info("[FETCH_TASK] %s: running", task_id)

        # 复用现有抓取逻辑
        result = check_announce(since_date="", mgr=mgr)

        now2 = datetime.now(timezone.utc).isoformat()
        if result.get("ok"):
            db.execute(
                "UPDATE fetch_task SET status='success', progress=100, result_data=?, updated_at=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), now2, task_id),
            )
            logger.info("[FETCH_TASK] %s: success (count=%d)", task_id, result.get("count", 0))
        else:
            db.execute(
                "UPDATE fetch_task SET status='failed', progress=100, error_msg=?, updated_at=? WHERE id=?",
                ("抓取完成但返回非 ok", now2, task_id),
            )
            logger.warning("[FETCH_TASK] %s: failed (not ok)", task_id)
    except Exception as e:
        now3 = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE fetch_task SET status='failed', progress=50, error_msg=?, updated_at=? WHERE id=?",
            (str(e), now3, task_id),
        )
        logger.exception("[FETCH_TASK] %s: exception", task_id)
    finally:
        db.close()


@router.post("/api/announcements/fetch")
def trigger_fetch(body: dict = {}, mgr=Depends(get_manager_dep)):
    """触发异步公告抓取。可选 adapter_name（不传则抓取全部）。
    立即返回 task_id，后台线程执行抓取。
    """
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    task_id = uuid.uuid4().hex
    adapter_name = body.get("adapter_name", "")
    now = datetime.now(timezone.utc).isoformat()

    db = Database(get_db_path())
    db.execute(
        "INSERT INTO fetch_task (id, task_type, status, progress, created_at, updated_at) "
        "VALUES (?, 'announcement', 'pending', 0, ?, ?)",
        (task_id, now, now),
    )
    db.close()

    logger.info("[FETCH_TASK] %s: created (adapter=%s)", task_id, adapter_name or "all")

    # 启动后台线程
    t = threading.Thread(target=_run_fetch_task, args=(task_id, adapter_name, mgr), daemon=True)
    t.start()

    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"任务已创建，请轮询 /api/announcements/status/{task_id} 查询进度",
    }


@router.get("/api/announcements/status/{task_id}")
def get_task_status(task_id: str):
    """查询异步抓取任务进度。"""
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    db = Database(get_db_path())
    row = db.fetchone("SELECT * FROM fetch_task WHERE id=?", (task_id,))
    db.close()
    if row is None:
        return JSONResponse({"error": "任务不存在"}, 404)
    return {
        "task_id": row["id"],
        "status": row["status"],
        "progress": row["progress"],
        "error_msg": row["error_msg"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.get("/api/announcements/results/{task_id}")
def get_task_results(task_id: str):
    """获取异步抓取任务的结果数据。"""
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    db = Database(get_db_path())
    row = db.fetchone("SELECT * FROM fetch_task WHERE id=?", (task_id,))
    db.close()
    if row is None:
        return JSONResponse({"error": "任务不存在"}, 404)

    status = row["status"]
    if status == "success":
        data = {}
        if row["result_data"]:
            try:
                data = json.loads(row["result_data"])
            except (json.JSONDecodeError, TypeError):
                pass
        return {"task_id": task_id, "status": "success", "data": data}
    elif status in ("pending", "running"):
        return JSONResponse(
            {"task_id": task_id, "status": status, "message": "任务尚未完成，请稍后再试"},
            202,
        )
    else:
        return JSONResponse(
            {
                "task_id": task_id,
                "status": status,
                "error": row["error_msg"] or "任务执行失败",
            },
            500,
        )
