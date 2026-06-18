# pilotstd/manager/ — StandardManager 门面 + 子服务模块
# 服务类提取自原 pilotstd/manager.py，保持门面模式向后兼容

from .announce_service import AnnounceService
from .classifier import QueryClassifier
from .facade import StandardManager
from .organizer_service import OrganizerService
from .pending_service import PendingService
from .scheduled_service import ScheduledService
from .service_factory import create_services

__all__ = [
    "StandardManager",
    "QueryClassifier",
    "OrganizerService",
    "AnnounceService",
    "PendingService",
    "ScheduledService",
    "create_services",
]
