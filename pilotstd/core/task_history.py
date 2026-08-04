# 模块：项目/核心/_脚本
# 阶段2:定时任务执行历史持久化—写入数据库+自动清理+查询

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_db_path
from .db.database import Database
from .task_status import record_task_result

logger = logging.getLogger(__name__)

# 清理节流：每___次写入触发一次清理
_CLEANUP_EVERY_N = 10
_write_count = 0
_cleanup_lock = threading.Lock()

# 测试注入：允许外部设置数据库实例覆盖（仅用于测试）
_db_override: Optional[Database] = None


def _set_db_override(db: Optional[Database]) -> None:
    """设置 DB 覆盖实例（仅测试使用）。传 None 恢复默认。"""
    global _db_override
    _db_override = db


def _get_db() -> Database:
    """返回 DB 实例：优先使用测试覆盖，否则创建默认连接。"""
    if _db_override is not None:
        return _db_override
    return Database(get_db_path())


def write_execution_record(
    task_name: str,
    status: str,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """写入执行记录到 DB，同步更新 Phase1 内存缓存，触发清理。

    此函数被 task_status.capture_task_error 装饰器调用。
    """
    db = _get_db()
    finished_at = datetime.now(timezone.utc).isoformat()

    try:
        db.execute(
            "INSERT INTO task_execution_history"
            " (task_name, status, error_message, finished_at, duration_ms)"
            " VALUES (?, ?, ?, ?, ?)",
            (task_name, status, error_message, finished_at, duration_ms),
        )
    except Exception:
        logger.exception("写入 task_execution_history 失败: %s", task_name)
        return

    # 同步更新阶段1内存缓存（保持向前兼容）
    record_task_result(task_name, status, error_message)

    # 节流清理
    _cleanup_if_needed(db)


def _cleanup_if_needed(db: Database) -> None:
    """双条件清理：30天过期 + 单任务 ≤2000条。每 N 次写入触发一次。"""
    global _write_count
    _write_count += 1
    if _write_count % _CLEANUP_EVERY_N != 0:
        return

    # 非阻塞尝试获取锁，其他线程已在清理则跳过
    if not _cleanup_lock.acquire(blocking=False):
        return
    try:
        # 条件1：删除 30 天前的记录
        db.execute("DELETE FROM task_execution_history WHERE finished_at < datetime('now', '-30 days')")
        # 条件2：每个任务保留最新 2000 条
        tasks = db.fetchall(
            "SELECT DISTINCT task_name FROM task_execution_history GROUP BY task_name HAVING COUNT(*) > 2000"
        )
        for row in tasks:
            name = row["task_name"]
            db.execute(
                "DELETE FROM task_execution_history WHERE task_name = ? AND id NOT IN ("
                "  SELECT id FROM task_execution_history WHERE task_name = ?"
                "  ORDER BY finished_at DESC LIMIT 2000"
                ")",
                (name, name),
            )
    except Exception:
        logger.exception("task_execution_history 清理失败")
    finally:
        _cleanup_lock.release()


def get_task_history(
    task_name: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """分页查询执行历史，支持按 task_name 过滤。

    返回 {total, page, size, items: [...]}。
    """
    db = _get_db()
    page = max(1, page)
    size = min(max(1, size), 100)
    offset = (page - 1) * size

    if task_name:
        total_row = db.fetchone(
            "SELECT COUNT(*) AS cnt FROM task_execution_history WHERE task_name = ?",
            (task_name,),
        )
        rows = db.fetchall(
            "SELECT * FROM task_execution_history WHERE task_name = ? ORDER BY finished_at DESC LIMIT ? OFFSET ?",
            (task_name, size, offset),
        )
    else:
        total_row = db.fetchone("SELECT COUNT(*) AS cnt FROM task_execution_history")
        rows = db.fetchall(
            "SELECT * FROM task_execution_history ORDER BY finished_at DESC LIMIT ? OFFSET ?",
            (size, offset),
        )

    total = total_row["cnt"] if total_row else 0
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [dict(r) for r in rows],
    }


def get_task_stats() -> list[dict[str, Any]]:
    """获取每个任务的聚合统计：成功率、平均耗时、最近错误、最近成功时间。"""
    db = _get_db()
    rows = db.fetchall(
        "SELECT"
        "  task_name,"
        "  COUNT(*) AS total_count,"
        "  CAST(SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS REAL) / COUNT(*) AS success_rate,"
        "  CAST(AVG(CASE WHEN duration_ms IS NOT NULL THEN duration_ms END) AS INTEGER) AS avg_duration_ms,"
        "  (SELECT error_message FROM task_execution_history t2"
        "   WHERE t2.task_name = t1.task_name AND t2.status = 'error'"
        "   ORDER BY t2.finished_at DESC LIMIT 1) AS last_error,"
        "  (SELECT finished_at FROM task_execution_history t3"
        "   WHERE t3.task_name = t1.task_name AND t3.status = 'success'"
        "   ORDER BY t3.finished_at DESC LIMIT 1) AS last_success"
        " FROM task_execution_history t1"
        " GROUP BY task_name"
        " ORDER BY task_name"
    )
    return [dict(r) for r in rows]
