# pilotstd/announcement/adapters/samr_hb.py
# SAMR 行业标准公告适配器

from ..base import BaseAnnounceAdapter


class SamrHbAdapter(BaseAnnounceAdapter):
    """SAMR 行业标准公告适配器。"""

    @property
    def site_name(self) -> str:
        return "samr_hb"

    @property
    def standard_type(self) -> str:
        return "hb"

    @property
    def _list_url(self) -> str:
        return "https://std.samr.gov.cn/noc/search/nocHBPage"

    @property
    def _detail_url(self) -> str:
        return "https://std.sacinfo.org.cn/gnocHb/queryInfo"
