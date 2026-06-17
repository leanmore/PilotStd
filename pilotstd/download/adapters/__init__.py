# pilotstd/download/adapters/__init__.py
from .base import BaseDownloadAdapter
from .openstd_download import OpenstdDownloadAdapter

try:
    from .mock import MockDownloadAdapter
except ImportError:
    MockDownloadAdapter = None

__all__ = ["BaseDownloadAdapter", "OpenstdDownloadAdapter"]
if MockDownloadAdapter is not None:
    __all__.append("MockDownloadAdapter")
