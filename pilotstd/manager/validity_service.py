# pilotstd/manager/validity_service.py
# 时效性检查服务 — 供 API 层调用

from typing import Any


class ValidityService:
    """时效性检查业务逻辑。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def get_history(self, page: int = 1, size: int = 20) -> dict[str, Any]:
        """获取时效性检查历史记录（分页）。"""
        db = self._mgr.db
        offset = (page - 1) * size
        total = db.fetchone(
            "SELECT COUNT(DISTINCT DATE(last_checked_at)) AS cnt "
            "FROM standard_validity WHERE last_checked_at IS NOT NULL"
        )
        rows = db.fetchall(
            "SELECT DATE(last_checked_at) AS check_date, "
            "COUNT(*) AS checked_count, "
            "SUM(CASE WHEN last_status != status THEN 1 ELSE 0 END) AS changed_count "
            "FROM standard_validity "
            "WHERE last_checked_at IS NOT NULL "
            "GROUP BY DATE(last_checked_at) "
            "ORDER BY check_date DESC LIMIT ? OFFSET ?",
            (size, offset),
        )
        return {
            "total": total["cnt"] if total else 0,
            "page": page,
            "page_size": size,
            "items": [
                {
                    "check_date": r["check_date"],
                    "checked_count": r["checked_count"],
                    "changed_count": r["changed_count"],
                    "status": "success",
                }
                for r in rows
            ],
        }

    def enqueue_files(self, file_paths: list[str]) -> dict[str, Any]:
        """将文件路径列表加入时效性检查队列。"""
        db = self._mgr.db
        inserted = 0
        for fp in file_paths:
            try:
                db.execute(
                    "INSERT OR IGNORE INTO validity_check_queue "
                    "(file_path, status, created_at) VALUES (?, 'pending', datetime('now', 'localtime'))",
                    (str(fp),),
                )
                inserted += 1
            except Exception:
                pass
        return {"ok": True, "enqueued": inserted, "total": len(file_paths)}
