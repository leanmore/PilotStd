# 模块：pilotstd/manager/system_service.py
# 系统状态服务 — 供 API 层迁移使用

from typing import Any


class SystemService:
    """系统状态（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def get_status(self) -> dict[str, Any]:
        """获取系统状态信息。"""
        db = self._mgr.db
        total = db.fetchone("SELECT COUNT(*) AS cnt FROM standard_validity")
        return {
            "total_standards": total["cnt"] if total else 0,
            "db_connected": True,
        }
