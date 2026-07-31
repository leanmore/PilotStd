# pilotstd/query/adapters/mock.py
# 模拟查询适配器（用于 UI 调试，后续替换为真实网站适配器）

from typing import Optional

from pilotstd.query.adapters.base import BaseAdapter
from pilotstd.query.models import QueryResult


class MockQueryAdapter(BaseAdapter):
    """模拟查询适配器，返回固定现行状态的 QueryResult。"""

    @property
    def site_name(self) -> str:
        return "mock_query"

    @property
    def site_label(self) -> str:
        return "模拟查询站点"

    def _search(self, search_term: str) -> Optional[QueryResult]:
        return QueryResult(
            standard_number=search_term,
            standard_name=f"标准名称_{search_term}",
            status="现行",
            replaces="",
            implementation_date="2024-07-01",
            publish_date="2024-01-15",
            abolition_date="",
            responsible_dept="全国标准化技术委员会",
            is_adopted=False,
            source_site=self.site_name,
            is_downloadable=True,
            match_status="exact",
        )
