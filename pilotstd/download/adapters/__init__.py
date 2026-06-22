# pilotstd/download/adapters/__init__.py
from .base import BaseDownloadAdapter
from .openstd_download import OpenstdDownloadAdapter

__all__ = ["BaseDownloadAdapter", "OpenstdDownloadAdapter"]
