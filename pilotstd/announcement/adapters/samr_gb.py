# 模块：项目//适配器/_脚本
# 国家标准公告适配器

from ..base import BaseAnnounceCrawler


class SamrGbCrawler(BaseAnnounceCrawler):
    """SAMR 国家标准公告适配器。"""

    @property
    def site_name(self) -> str:
        return "samr_gb"

    @property
    def standard_type(self) -> str:
        return "gb"

    @property
    def standard_category(self) -> str:
        """收藏分类：国家标准。"""
        return "NationalStd"

    @property
    def _list_url(self) -> str:
        return "https://std.samr.gov.cn/noc/search/nocGBPage"

    @property
    def _detail_url(self) -> str:
        return "https://std.sacinfo.org.cn/gnoc/queryInfo"
