# pilotstd/announcement/adapters/__init__.py
# 适配器注册中心

from .samr_gb import SamrGbAdapter
from .samr_hb import SamrHbAdapter
from .samr_db import SamrDbAdapter

__all__ = ["SamrGbAdapter", "SamrHbAdapter", "SamrDbAdapter"]
