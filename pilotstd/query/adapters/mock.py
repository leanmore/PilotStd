# pilotstd/query/adapters/mock.py
# 模拟查询适配器（用于 UI 调试，后续替换为真实网站适配器）

import random
from typing import Optional

from ..models import QueryResult
from .base import BaseAdapter

STATUS_POOL = ["现行", "现行", "现行", "现行", "废止", "即将实施"]
DEPT_POOL = [
    "全国标准化技术委员会",
    "国家市场监督管理总局",
    "工业和信息化部",
    "住房和城乡建设部",
    "交通运输部",
    "国家卫生健康委员会",
]
DATES = ["2020-07-01", "2021-03-01", "2022-10-15", "2019-06-01", "2023-01-01"]


class MockQueryAdapter(BaseAdapter):
    """模拟查询适配器，返回随机生成的 QueryResult。"""

    @property
    def site_name(self) -> str:
        return "mock_query"

    @property
    def site_label(self) -> str:
        return "模拟查询站点"

    def _search(self, search_term: str) -> Optional[QueryResult]:
        status = random.choice(STATUS_POOL)
        is_adopted = random.random() < 0.15
        return QueryResult(
            standard_number=search_term,
            standard_name=f"标准名称_{search_term}",
            status=status,
            replaces="",
            implementation_date=random.choice(DATES),
            publish_date=random.choice(DATES),
            abolition_date=random.choice(DATES) if status in ("废止", "作废") else "",
            responsible_dept=random.choice(DEPT_POOL),
            is_adopted=is_adopted,
            source_site=self.site_name,
            is_downloadable=not is_adopted,
        )
