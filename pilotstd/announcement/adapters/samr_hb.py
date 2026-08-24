# 模块：项目//适配器/_脚本
# 行业标准公告适配器

from ..base import BaseAnnounceCrawler


class SamrHbCrawler(BaseAnnounceCrawler):
    """SAMR 行业标准公告适配器。"""

    @property
    def site_name(self) -> str:
        return "samr_hb"

    @property
    def standard_type(self) -> str:
        return "hb"

    @property
    def standard_category(self) -> str:
        """收藏分类：行业标准统称桶。"""
        return "IndustryStd"

    @property
    def _list_url(self) -> str:
        return "https://std.samr.gov.cn/noc/search/nocHBPage"

    @property
    def _detail_url(self) -> str:
        return "https://std.sacinfo.org.cn/gnocHb/queryInfo"
