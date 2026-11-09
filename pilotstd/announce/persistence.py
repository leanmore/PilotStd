# 模块：项目//持久化脚本
"""Fetch checkpoint, failure log, and async task persistence.

Compatible with both Database (fetchone/execute returning dicts) and
raw sqlite3 (cursor-based). Rows are accessed by column name in both.
"""

from __future__ import annotations

from typing import Any

from pilotstd.core.time_utils import iso_now


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

    def _query_all(self, sql: str, params: tuple = ()) -> list[Any]:
        """执行 SELECT 查询并返回全部行（dict 或 sqlite3.Row）。"""
        if hasattr(self._db, "fetchall"):
            return list(self._db.fetchall(sql, params))
        cur = self._db.execute(sql, params)
        return list(cur.fetchall())

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """把 dict / sqlite3.Row 统一成 dict。"""
        if isinstance(row, dict):
            return row
        return dict(row)

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

    def write_checkpoint(self, source_site: str, last_notice_date: str, *, force: bool = False) -> None:
        """写入检查点；默认防回退，失败回退时由调用方传 force=True。"""
        if not last_notice_date:
            return
        current = self._query_one(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?",
            (source_site,),
        )
        if not force and current and current["last_notice_date"] >= last_notice_date:
            return
        now = iso_now()
        self._exec(
            "INSERT OR REPLACE INTO fetch_checkpoint "
            "(source_site, last_fetched_at, last_notice_date) VALUES (?, ?, ?)",
            (source_site, now, last_notice_date),
        )

    # -- 失败日志 ------------------------------------------------

    def record_failure(self, source_site: str, error_msg: str) -> None:
        """记录获取失败到 fetch_failures 表。"""
        self._exec(
            "INSERT INTO fetch_failures (task_type, source_site, since_date, error_message) "
            "VALUES (?, ?, ?, ?)",
            ("scheduled", source_site, "", error_msg),
        )

    def list_failures(self, limit: int = 20, unresolved_only: bool = False) -> list[dict[str, Any]]:
        """读取抓取失败历史（最新在前）；unresolved_only 只看未解决。

        P1-03：本表此前只写不读。读侧供公告页/诊断使用，而不是只留在 DB。
        """
        # 只取展示需要的列，避免把未来新增的大字段带进列表
        sql = (
            "SELECT id, task_type, source_site, error_message, retry_count, "
            "resolved, created_at, last_retry_at FROM fetch_failures"
        )
        params: list[Any] = []
        if unresolved_only:
            # resolved 历史值可能为 NULL，统一按“未解决”处理
            sql += " WHERE COALESCE(resolved, 0) = 0"
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 100)))
        return [self._row_to_dict(r) for r in self._query_all(sql, tuple(params))]

    def failure_counts(self) -> dict[str, int]:
        """返回失败总数与未解决数（供页面角标/诊断）。"""
        # 一次查询同时取总数与未解决数，避免页面两次往返
        row = self._query_one(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN COALESCE(resolved, 0) = 0 THEN 1 ELSE 0 END) AS unresolved "
            "FROM fetch_failures"
        )
        if row is None:
            return {"total": 0, "unresolved": 0}
        data = self._row_to_dict(row)
        return {
            "total": int(data.get("total") or 0),
            "unresolved": int(data.get("unresolved") or 0),
        }

    def resolve_failure(self, failure_id: int) -> int:
        """把一条失败标记为已解决；返回受影响行数（供后续重试/人工确认）。"""
        cur = self._db.execute(
            "UPDATE fetch_failures SET resolved = 1 WHERE id = ?",
            (failure_id,),
        )
        return int(getattr(cur, "rowcount", 0) or 0)

    def resolve_site_failures(self, source_site: str) -> int:
        """某站点本轮抓取成功 → 把该站点所有未解决失败标记为已解决。"""
        cur = self._db.execute(
            "UPDATE fetch_failures SET resolved = 1 "
            "WHERE source_site = ? AND COALESCE(resolved, 0) = 0",
            (source_site,),
        )
        return int(getattr(cur, "rowcount", 0) or 0)

    # -- 异步任务 ------------------------------------------------

    def create_task(self, task_id: str) -> None:
        """插入一条新的 fetch_task 行，状态为 'pending'。"""
        now = iso_now()
        self._exec(
            "INSERT INTO fetch_task (id, task_type, status, progress, created_at, updated_at) "
            "VALUES (?, 'announcement', 'pending', 0, ?, ?)",
            (task_id, now, now),
        )

    def update_task(self, task_id: str, status: str, progress: int,
                    error_msg: str = "") -> None:
        """更新 fetch_task 的状态和进度，可选设置错误信息。"""
        now = iso_now()
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
