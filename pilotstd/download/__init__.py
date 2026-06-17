from .models import DownloadTask, DownloadStatus, BatchDownloadStats
from .adapters.base import BaseDownloadAdapter
from .adapters.openstd_download import OpenstdDownloadAdapter
from .session import SessionManager
from .engine import DownloadEngine

try:
    from .adapters.mock import MockDownloadAdapter
except ImportError:
    MockDownloadAdapter = None

__all__ = [
    "DownloadTask",
    "DownloadStatus",
    "BatchDownloadStats",
    "BaseDownloadAdapter",
    "OpenstdDownloadAdapter",
    "SessionManager",
    "DownloadEngine",
]
if MockDownloadAdapter is not None:
    __all__.append("MockDownloadAdapter")
