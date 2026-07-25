# pilotstd/manager/standard_service.py
# 标准统计与列表查询服务 — 统一数据源为 file_index

from typing import Any


class StandardService:
    """标准统计与列表查询（数据源：file_index，与首页卡片口径一致）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    # ── 状态映射：前端筛选值 → file_index 实际值 ──

    @staticmethod
    def _map_filter_status(filter_status: str) -> tuple[list[str], str | None]:
        """将前端筛选状态值映射到 file_index 的 WHERE 子句。
        Returns: (values_list, operator) — operator 为 'IN'/'NOT IN'/None(=)
        """
        if filter_status == "现行":
            return (["现行"], None)
        if filter_status == "已废止":
            return (["废止", "被代替"], "IN")
        if filter_status == "未知":
            return (["现行", "废止", "被代替"], "NOT IN")
        return ([filter_status], None)

    @staticmethod
    def _build_where(filters: dict[str, Any] | None) -> tuple[str, list[Any]]:
        """构建 file_index 查询的 WHERE 子句，与首页卡片过滤条件一致。"""
        clauses = ["status IS NOT NULL"]
        params: list[Any] = []
        if not filters:
            return "WHERE " + " AND ".join(clauses), params

        if filters.get("status"):
            values, op = StandardService._map_filter_status(filters["status"])
            if op == "IN":
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"status IN ({placeholders})")
                params.extend(values)
            elif op == "NOT IN":
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"status NOT IN ({placeholders})")
                params.extend(values)
            else:
                clauses.append("status = ?")
                params.append(values[0])

        if filters.get("keyword"):
            clauses.append("((logical_code || ' ' || number) LIKE ? OR std_name LIKE ?)")
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw])

        return "WHERE " + " AND ".join(clauses), params

    # ── 统计 ──

    def get_stats(self) -> dict[str, Any]:
        """获取标准统计信息（按状态分组计数），数据源 file_index。
        SQL 与首页卡片 get_status_stats() 完全一致。
        """
        db = self._mgr.db
        rows = db.fetchall("SELECT status, COUNT(*) AS cnt FROM file_index WHERE status IS NOT NULL GROUP BY status")
        s = {row["status"]: row["cnt"] for row in rows}
        by_status = {
            "现行": s.get("现行", 0),
            "已废止": s.get("废止", 0) + s.get("被代替", 0),
            "未知": sum(cnt for st, cnt in s.items() if st not in ("现行", "废止", "被代替")),
        }
        return {
            "total": sum(by_status.values()),
            "by_status": by_status,
        }

    # ── 列表 ──

    def get_list(
        self,
        page: int = 1,
        size: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """获取标准状态列表（分页 + 可选过滤），数据源 file_index。"""
        db = self._mgr.db
        offset = (page - 1) * size

        where_sql, params = self._build_where(filters)

        total = db.fetchone(f"SELECT COUNT(*) AS cnt FROM file_index {where_sql}", tuple(params))

        # 构造 standard_number 字段，兼容原 standard_validity 接口契约
        rows = db.fetchall(
            f"SELECT id, (logical_code || ' ' || number) AS standard_number, status,"
            f" NULL AS last_checked_at, NULL AS next_check_at, 0 AS check_count"
            f" FROM file_index {where_sql}"
            f" ORDER BY logical_code, number, part LIMIT ? OFFSET ?",
            tuple(params + [size, offset]),
        )

        return {
            "items": rows,
            "total": total["cnt"] if total else 0,
            "page": page,
            "size": size,
        }
