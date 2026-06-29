# pilotstd/manager/monitor_service.py
# 文件监控服务 — 供 API 层 + app.py 生命周期使用

from typing import Any


class MonitorService:
    """文件系统监控服务（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def get_config(self) -> dict[str, Any]:
        """获取文件监控配置。"""
        from pilotstd.monitor.config import get_config

        return get_config()

    def set_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """更新文件监控配置。"""
        from pilotstd.monitor.config import set_config

        set_config(body)
        return {"ok": True}

    def get_status(self) -> dict[str, Any]:
        """获取监控运行状态。"""
        from pilotstd.monitor.scheduler import get_scheduler

        return get_scheduler().get_status()

    def start(self) -> dict[str, Any]:
        """启动文件监控。"""
        from pilotstd.monitor.scheduler import get_scheduler

        scheduler = get_scheduler()
        scheduler.start()
        return {"ok": True, "running": scheduler.running}

    def stop(self) -> dict[str, Any]:
        """停止文件监控。"""
        from pilotstd.monitor.scheduler import get_scheduler

        scheduler = get_scheduler()
        scheduler.stop()
        return {"ok": True, "running": False}

    # ── app.py 生命周期专用 ─────────────────────────────────

    def start_scheduler(self) -> None:
        """启动监控调度器（app.py lifespan 用）。"""
        from pilotstd.monitor.scheduler import get_scheduler

        get_scheduler().start()

    def stop_scheduler(self) -> None:
        """停止监控调度器（app.py lifespan 用）。"""
        from pilotstd.monitor.scheduler import get_scheduler

        get_scheduler().stop()
