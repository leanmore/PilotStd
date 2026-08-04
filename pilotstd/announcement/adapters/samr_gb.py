# 模块：pilotstd/announcement/adapters/samr_gb.py
# SAMR 国家标准公告适配器

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
    def _list_url(self) -> str:
        return "https://std.samr.gov.cn/noc/search/nocGBPage"

    @property
    def _detail_url(self) -> str:
        return "https://std.sacinfo.org.cn/gnoc/queryInfo"
