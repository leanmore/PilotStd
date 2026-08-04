# 模块：pilotstd/announce/persistence.py
"""Fetch checkpoint, failure log, and async task persistence.

Compatible with both Database (fetchone/execute returning dicts) and
raw sqlite3 (cursor-based). Rows are accessed by column name in both.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class AnnouncePersistence:
    """检查点、失败日志和异步任务状态的 SQL 持久化。"""

    def __init__(self, db: Any):
        self._db = db

    def _query_one(self, sql: str, params: tuple = ()) -> Any:
        """执行 SELECT 查询并返回单行（dict 或 sqlite3.Row）。"""
        if hasattr(self._db, "fetchone"):
            return self._db.fetchone(sql, params)
        cur = self._db.execute(sql, params)
        return cur.fetchone()

    def _exec(self, sql: str, params: tuple = ()) -> None:
        """执行 DML（INSERT/UPDATE/DELETE），双后端兼容。"""
        if hasattr(self._db, "fetchone"):
            self._db.execute(sql, params)
        else:
            self._db.execute(sql, params)

    # -- 检查点 -------------------------------------------------

    def get_checkpoint(self, source_site: str) -> str | None:
        """返回 source_site 的 last_notice_date，未找到则返回 None。"""
        row = self._query_one(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?",
            (source_site,),
        )
        if row is None:
            return None
        return row["last_notice_date"] or None

    def write_checkpoint(self, source_site: str, last_notice_date: str) -> None:
        """写入检查点，含防回退保护（更旧的日期将被忽略）。"""
        if not last_notice_date:
            return
        current = self._query_one(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?",
            (source_site,),
        )
        if current and current["last_notice_date"] >= last_notice_date:
            return
        now = datetime.now().isoformat()
        self._exec(
            "INSERT OR REPLACE INTO fetch_checkpoint "
            "(source_site, last_fetched_at, last_notice_date) VALUES (?, ?, ?)",
            (source_site, now, last_notice_date),
        )

    # -- 失败日志 ------------------------------------------------

    def record_failure(self, source_site: str, error_msg: str) -> None:
        """记录获取失败到 fetch_failures 表。"""
        now = datetime.now().isoformat()
        self._exec(
            "INSERT INTO fetch_failures (task_type, source_site, since_date, error_message) "
            "VALUES (?, ?, ?, ?)",
            ("scheduled", source_site, "", error_msg),
        )

    # -- 异步任务 ------------------------------------------------

    def create_task(self, task_id: str) -> None:
        """插入一条新的 fetch_task 行，状态为 'pending'。"""
        now = datetime.now().isoformat()
        self._exec(
            "INSERT INTO fetch_task (id, task_type, status, progress, created_at, updated_at) "
            "VALUES (?, 'announcement', 'pending', 0, ?, ?)",
            (task_id, now, now),
        )

    def update_task(self, task_id: str, status: str, progress: int,
                    error_msg: str = "") -> None:
        """更新 fetch_task 的状态和进度，可选设置错误信息。"""
        now = datetime.now().isoformat()
        if error_msg:
            self._exec(
                "UPDATE fetch_task SET status=?, progress=?, error_msg=?, updated_at=? "
                "WHERE id=?",
                (status, progress, error_msg, now, task_id),
            )
        else:
            self._exec(
                "UPDATE fetch_task SET status=?, progress=?, updated_at=? WHERE id=?",
                (status, progress, now, task_id),
            )
