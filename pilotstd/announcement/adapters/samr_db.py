# pilotstd/announcement/adapters/samr_db.py
# SAMR 地方标准公告适配器（详情页使用 gnocDb 独立端点）

from ..base import BaseAnnounceAdapter


class SamrDbAdapter(BaseAnnounceAdapter):
    """SAMR 地方标准公告适配器。"""

    @property
    def site_name(self) -> str:
        return "samr_db"

    @property
    def standard_type(self) -> str:
        return "db"

    @property
    def _list_url(self) -> str:
        return "https://std.samr.gov.cn/noc/search/nocDBPage"

    @property
    def _detail_url(self) -> str:
        return "https://std.sacinfo.org.cn/gnocDb/queryInfo"
