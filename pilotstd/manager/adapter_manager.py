# 模块：项目/管理器/适配器_管理器脚本
# 适配器状态管理器—聚合++适配器_表

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


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
                    "SELECT frozen_until, freeze_count, fail_streak FROM adapter_state WHERE adapter_name = ?",
                    (name,),
                )
            except Exception:
                pass

        remaining = 0
        if site_state and site_state.cooldown_until > 0:
            remaining = max(0, site_state.cooldown_until - time.time())

        # 应用层推导（适配器_表无列）
        h_status = "normal"
        if health:
            frozen_until = health["frozen_until"]
            if frozen_until:
                try:
                    from datetime import datetime as _dt

                    frozen_dt = _dt.fromisoformat(frozen_until)
                    if frozen_dt.timestamp() > time.time():
                        h_status = "frozen"
                except (ValueError, TypeError, OSError):
                    pass
            if h_status == "normal" and health.get("fail_streak", 0) > 0:
                h_status = "degraded"

        return {
            "name": name,
            "status": health and h_status or "normal",
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

    def get_all_health(self) -> list[dict[str, Any]]:
        """返回 adapter_state 表全部原始行（供 API 层迁移）。"""
        if not self._db:
            return []
        try:
            rows = self._db.fetchall("SELECT * FROM adapter_state")
            return [dict(r) for r in rows]
        except Exception:
            return []

    # 阶段3.1:_执行层落地
    def get_request_interval(self, name: str) -> float:
        """返回指定站点的请求间隔（秒），未注册返回 0。"""
        if self._rotator and name in self._rotator._sites:
            return float(self._rotator._sites[name].request_interval)
        return 0.0

    def execute_request_interval(self, name: str) -> None:
        """执行 request_interval 等待（在每次适配器查询前调用）。

        从 SiteState.request_interval 读取间隔值并 time.sleep。
        若值为 0 或站点不存在则跳过。
        """
        interval = self.get_request_interval(name)
        if interval > 0:
            time.sleep(interval)
            logger.debug("request_interval_wait: site=%s interval=%.1fs", name, interval)

    def test_adapter(self, name: str) -> dict[str, Any]:
        """测试单个适配器连通性。"""
        if name not in self.list_adapters():
            return {"ok": False, "message": f"适配器 {name} 不存在"}
        status = self.get_adapter_status(name)
        return {
            "ok": status.get("status") == "normal",
            "message": f"适配器 {name}: {status.get('status', 'unknown')}",
            "details": status,
        }
