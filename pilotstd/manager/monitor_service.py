# 模块：项目/管理器/_服务脚本
# 文件监控服务—供接口层+脚本生命周期使用

import logging
from datetime import date
from typing import Any, cast

logger = logging.getLogger(__name__)


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    import secrets

    return secrets.token_hex(4)


class MonitorService:
    """文件系统监控服务（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def get_config(self) -> dict[str, Any]:
        """获取文件监控配置。"""
        from pilotstd.monitor.config import get_config

        return get_config()

    def set_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """更新文件监控配置，并根据服务状态决定启动或重启（批次4-D组热更新）。"""
        from pilotstd.monitor.config import get_config, set_config
        from pilotstd.monitor.scheduler import get_scheduler

        set_config(body)
        new_config = get_config()
        scheduler = get_scheduler()
        # 配置写入后，根据服务状态决定启动或重启
        if scheduler.running:
            try:
                scheduler.stop()
                scheduler.start()
                logger.info(
                    "监控服务已重启: trace_id=%s source_type=monitor_service target_chat_id=-",
                    _log_trace_id(),
                )
            except Exception:
                logger.error(
                    "监控服务重启失败: trace_id=%s source_type=monitor_service target_chat_id=-",
                    _log_trace_id(),
                    exc_info=True,
                )
        elif new_config.get("enabled", True):
            # 服务未运行但 enabled=true → 启动
            scheduler.start()
        return {"ok": True}

    def get_status(self) -> dict[str, Any]:
        """获取监控运行状态。"""
        from pilotstd.monitor.scheduler import get_scheduler

        return cast("dict[str, Any]", get_scheduler().get_status())

    def get_stats(self) -> dict[str, Any]:
        """获取当天监控统计。"""
        from pilotstd.monitor.config import get_monitor_stats

        stats = get_monitor_stats().get_today_stats()
        return {
            "date": date.today().isoformat(),
            "processed": stats["processed"],
            "success": stats["success"],
            "failed": stats["failed"],
        }

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

    # ──脚本生命周期专用─────────────────────────────────

    def start_scheduler(self) -> None:
        """启动监控调度器（app.py lifespan 用）。"""
        from pilotstd.monitor.scheduler import get_scheduler

        get_scheduler().start()

    def stop_scheduler(self) -> None:
        """停止监控调度器（app.py lifespan 用）。"""
        from pilotstd.monitor.scheduler import get_scheduler

        get_scheduler().stop()
