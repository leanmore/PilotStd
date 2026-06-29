# pilotstd/manager/adapter_manager.py
# 适配器状态管理器 — 聚合 SiteRotator + DailyQuotaTracker + adapter_health 表

import time
from typing import Any


class AdapterManager:
    """适配器状态管理——聚合查询引擎的站点状态和数据库熔断状态。"""

    def __init__(self, db: Any, rotator: Any, quota_tracker: Any):
        self._db = db
        self._rotator = rotator
        self._quota = quota_tracker

    def list_adapters(self) -> list[str]:
        """返回所有已配置适配器名称。"""
        return list(self._rotator._sites.keys()) if self._rotator else []

    def get_adapter_status(self, name: str) -> dict[str, Any]:
        """返回单个适配器的综合状态。"""
        site_state = self._rotator._sites.get(name) if self._rotator else None
        daily_used = self._quota.get_used(name) if self._quota else 0
        daily_limit = self._quota._limits.get(name, 500) if self._quota else 500

        health = None
        if self._db:
            try:
                health = self._db.fetchone(
                    "SELECT status, frozen_until, freeze_count, fail_streak FROM adapter_health WHERE name = ?",
                    (name,),
                )
            except Exception:
                pass

        remaining = 0
        if site_state and site_state.cooldown_until > 0:
            remaining = max(0, site_state.cooldown_until - time.time())

        return {
            "name": name,
            "status": health["status"] if health else "normal",
            "frozen_until": health["frozen_until"] if health else None,
            "remaining_seconds": int(remaining),
            "freeze_count": health["freeze_count"] if health else 0,
            "fail_streak": health["fail_streak"] if health else 0,
            "daily_used": daily_used,
            "daily_limit": daily_limit,
        }

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """返回所有适配器状态。"""
        return {name: self.get_adapter_status(name) for name in self.list_adapters()}
