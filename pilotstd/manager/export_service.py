# 模块：pilotstd/manager/export_service.py
# 数据导出服务 — 供 API 层迁移使用

from typing import Any


class ExportService:
    """数据导出（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def get_standards_data(self, fmt: str = "csv") -> dict[str, Any]:
        """获取标准数据用于导出（默认 CSV 格式）。"""
        db = self._mgr.db
        rows = db.fetchall(
            "SELECT standard_number, status, last_checked_at FROM standard_validity ORDER BY last_checked_at DESC"
        )
        return {"items": rows, "count": len(rows), "format": fmt}
