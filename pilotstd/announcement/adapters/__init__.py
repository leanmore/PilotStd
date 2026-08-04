# 模块：项目//适配器/____脚本
# 适配器注册中心

from .samr_db import SamrDbCrawler
from .samr_gb import SamrGbCrawler
from .samr_hb import SamrHbCrawler

__all__ = ["SamrGbCrawler", "SamrHbCrawler", "SamrDbCrawler"]
