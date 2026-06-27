# pilotstd/monitor/__init__.py
"""文件系统监控模块——基于 watchdog 实现 /inbox 自动扫描归档。"""

from .scheduler import FileMonitorScheduler

__all__ = ["FileMonitorScheduler"]
