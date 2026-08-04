# 模块：pilotstd/task/queue.py
# 任务队列：后台执行、断点续传（SQLite 持久化）、暂停/继续/取消

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..core.db import Database
from .models import TaskInfo, TaskStatus, TaskType

logger = logging.getLogger(__name__)

TASK_TABLE = "task_queue"
# TaskQueue — 后台任务队列，任务状态持久化到 SQLite，支持断点恢复
# 任务支持暂停/继续/取消，重启后自动将 running/pending 状态重置为 failed


class TaskQueue:
    """后台任务队列，任务状态持久化到 SQLite，支持断点恢复。"""

    def __init__(self, db: Database, task_timeout: int = 300) -> None:
        self._db = db
        self._lock = threading.Lock()
        self._handlers: Dict[TaskType, Callable[..., Any]] = {}
        self._task_timeout = task_timeout  # handler 超时秒数，超时后任务标记 FAILED
        self._ensure_table()

    # ---- 公共 API ----

    def register_handler(self, task_type: TaskType, handler: Callable[..., Any]) -> None:
        """注册任务类型的处理函数。handler(task: TaskInfo) -> TaskInfo"""
        self._handlers[task_type] = handler

    def enqueue(self, task_type: TaskType, total_items: int = 0) -> TaskInfo:
        """入队新任务，返回 TaskInfo。"""
        task = TaskInfo(
            task_id=uuid.uuid4().hex[:12],
            task_type=task_type,
            status=TaskStatus.PENDING,
            total_items=total_items,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self._persist(task)
        logger.info(f"任务入队: {task.task_id} [{task.task_type.value}]")
        return task

    def start(self, task: TaskInfo) -> None:
        """在后台线程中启动任务。"""
        handler = self._handlers.get(task.task_type)
        if handler is None:
            raise ValueError(f"未注册的处理类型: {task.task_type}")
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now().isoformat()
        self._persist(task)

        t = threading.Thread(target=self._run, args=(task, handler), daemon=True)
        t.start()

    def pause(self, task_id: str) -> bool:
        return self._set_status(task_id, TaskStatus.PAUSED)

    def resume(self, task: TaskInfo) -> None:
        """恢复已暂停的任务，重新标记为 RUNNING 并启动。"""
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now().isoformat()
        self._persist(task)
        self.start(task)

    def cancel(self, task_id: str) -> bool:
        return self._set_status(task_id, TaskStatus.CANCELLED)

    def get(self, task_id: str) -> Optional[TaskInfo]:
        """按任务 ID 查询单个任务。"""
        row = self._db.fetchone(f"SELECT * FROM {TASK_TABLE} WHERE task_id=?", (task_id,))
        return self._row_to_task(row) if row else None

    def get_all(self, status_filter: str | None = None, limit: int = 100) -> list[dict]:
        """返回所有任务的原始字典列表（供 API 层使用）。"""
        if status_filter:
            rows = self._db.fetchall(
                f"SELECT * FROM {TASK_TABLE} WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status_filter, limit),
            )
        else:
            rows = self._db.fetchall(f"SELECT * FROM {TASK_TABLE} ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def list_all(self, limit: int = 50) -> List[TaskInfo]:
        """返回最近更新的任务列表（默认 50 条）。"""
        rows = self._db.fetchall(f"SELECT * FROM {TASK_TABLE} ORDER BY updated_at DESC LIMIT ?", (limit,))
        return [self._row_to_task(r) for r in rows]

    def get_pending(self) -> List[TaskInfo]:
        """返回所有待处理或暂停状态的任务（按创建时间排序）。"""
        rows = self._db.fetchall(f"SELECT * FROM {TASK_TABLE} WHERE status IN ('pending','paused') ORDER BY created_at")
        return [self._row_to_task(r) for r in rows]

    def update_progress(self, task: TaskInfo, completed: int, failed: int = 0) -> None:
        """更新任务进度，全部完成时自动标记为 COMPLETED。"""
        with self._lock:
            task.completed_items = completed
            task.failed_items = failed
            if completed + failed >= task.total_items > 0:
                task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.now().isoformat()
            self._persist(task)

    # ---- 内部 ----

    def _run(self, task: TaskInfo, handler: Callable[..., Any]) -> None:
        result_holder = [None]
        exc_holder: list[Any] = [None]

        def wrapped_handler() -> None:
            """在独立线程中执行 handler，捕获异常存入 exc_holder。"""
            try:
                result_holder[0] = handler(task)
            except Exception as e:
                exc_holder[0] = e

        t = threading.Thread(target=wrapped_handler, daemon=True)
        t.start()
        t.join(timeout=self._task_timeout)

        if t.is_alive():
            # handler 仍在执行 → 超时
            logger.error("任务超时 (%ds): %s", self._task_timeout, task.task_id)
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error_log = f"任务超时 ({self._task_timeout}s)"
                task.updated_at = datetime.now().isoformat()
                self._persist(task)
            return

        if exc_holder[0] is not None:
            logger.exception("任务执行异常: %s", task.task_id)
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error_log = str(exc_holder[0])
                task.updated_at = datetime.now().isoformat()
                self._persist(task)
            return

        result = result_holder[0]
        with self._lock:
            r = result if isinstance(result, TaskInfo) else task
            if r.status not in (TaskStatus.CANCELLED, TaskStatus.FAILED):
                r.status = TaskStatus.COMPLETED
            r.updated_at = datetime.now().isoformat()
            self._persist(r)

    def _set_status(self, task_id: str, status: TaskStatus) -> bool:
        """加锁设置任务状态并持久化，返回是否成功。"""
        with self._lock:
            task = self.get(task_id)
            if task is None:
                return False
            task.status = status
            task.updated_at = datetime.now().isoformat()
            self._persist(task)
            return True

    def _persist(self, task: TaskInfo) -> None:
        """将任务信息写入 SQLite：已存在则更新，否则插入。"""
        existing = self._db.fetchone(f"SELECT id FROM {TASK_TABLE} WHERE task_id=?", (task.task_id,))
        data = (
            task.task_type.value,
            task.status.value,
            task.total_items,
            task.completed_items,
            task.failed_items,
            task.created_at,
            task.updated_at,
            task.result_json,
            task.error_log,
            task.task_id,
        )
        if existing:
            self._db.execute(
                f"UPDATE {TASK_TABLE} SET task_type=?, status=?, total_items=?, "
                "completed_items=?, failed_items=?, created_at=?, updated_at=?, "
                "result_json=?, error_log=? WHERE task_id=?",
                data,
            )
        else:
            self._db.execute(
                f"INSERT INTO {TASK_TABLE} (task_type, status, total_items, "
                "completed_items, failed_items, created_at, updated_at, "
                "result_json, error_log, task_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                data,
            )

    @staticmethod
    def _row_to_task(row: dict[str, Any]) -> TaskInfo:
        """将数据库行字典转换为 TaskInfo 对象。"""
        return TaskInfo(
            task_id=row["task_id"],
            task_type=TaskType(row["task_type"]),
            status=TaskStatus(row["status"]),
            total_items=row["total_items"],
            completed_items=row["completed_items"],
            failed_items=row["failed_items"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            result_json=row.get("result_json", ""),
            error_log=row.get("error_log", ""),
        )

    def _ensure_table(self) -> None:
        """确保任务队列表和索引存在，不存在则创建。"""
        self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS {TASK_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL UNIQUE,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                total_items INTEGER DEFAULT 0,
                completed_items INTEGER DEFAULT 0,
                failed_items INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result_json TEXT DEFAULT '',
                error_log TEXT DEFAULT ''
            )
        """)
        self._db.execute(f"CREATE INDEX IF NOT EXISTS idx_{TASK_TABLE}_status ON {TASK_TABLE}(status)")
        self._db.execute(f"CREATE INDEX IF NOT EXISTS idx_{TASK_TABLE}_updated ON {TASK_TABLE}(updated_at)")
        self._db.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{TASK_TABLE}_status_created ON {TASK_TABLE}(status, created_at)"
        )
