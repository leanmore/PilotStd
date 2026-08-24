# 模块：项目//适配器/_脚本
# 地方标准公告适配器（详情页使用独立端点）

from ..base import BaseAnnounceCrawler


class SamrDbCrawler(BaseAnnounceCrawler):
    """SAMR 地方标准公告适配器。"""

    @property
    def site_name(self) -> str:
        return "samr_db"

    @property
    def standard_type(self) -> str:
        return "db"

    @property
    def standard_category(self) -> str:
        """收藏分类：地方标准。"""
        return "LocalStd"

    @property
    def _list_url(self) -> str:
        return "https://std.samr.gov.cn/noc/search/nocDBPage"

    @property
    def _detail_url(self) -> str:
        return "https://std.sacinfo.org.cn/gnocDb/queryInfo"
