# pilotstd/manager/standard_service.py
# 标准统计与列表查询服务 — 供 API 层迁移使用

from typing import Any


class StandardService:
    """标准统计与列表查询（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def get_stats(self) -> dict[str, Any]:
        """获取标准统计信息（按状态分组计数）。"""
        db = self._mgr.db
        total = db.fetchone("SELECT COUNT(*) AS cnt FROM standard_validity")
        by_status = db.fetchall("SELECT status, COUNT(*) AS cnt FROM standard_validity GROUP BY status")
        return {
            "total": total["cnt"] if total else 0,
            "by_status": {row["status"]: row["cnt"] for row in by_status},
        }

    def get_list(self, page: int = 1, size: int = 20, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """获取标准列表（分页 + 可选过滤）。"""
        db = self._mgr.db
        offset = (page - 1) * size
        where_clauses: list[str] = []
        params: list[Any] = []
        if filters:
            if filters.get("status"):
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if filters.get("keyword"):
                where_clauses.append("standard_number LIKE ?")
                params.append(f"%{filters['keyword']}%")
        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total = db.fetchone(f"SELECT COUNT(*) AS cnt FROM standard_validity {where_sql}", tuple(params))
        rows = db.fetchall(
            f"SELECT * FROM standard_validity {where_sql} ORDER BY last_checked_at DESC LIMIT ? OFFSET ?",
            tuple(params + [size, offset]),
        )
        return {
            "items": rows,
            "total": total["cnt"] if total else 0,
            "page": page,
            "size": size,
        }
