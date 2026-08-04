"""Mock 适配器 — 用于测试和离线开发环境，返回预置假数据。"""

from typing import Any

from ..models import QueryResult
from .base import BaseAdapter


class MockQueryAdapter(BaseAdapter):
    """Mock 适配器，覆盖不同标准来源的字段填充特征。

    预设 4 条代表性假数据，分别模拟 std_gov / dbba / njbz365 / ahbz 的字段风格。
    """

    MOCK_DATA: list[dict[str, Any]] = [
        {
            # 模拟_风格：有，无
            "standard_number": "GB/T 12345-2024",
            "standard_name": "信息技术 测试标准规范",
            "status": "现行",
            "replaces": "",
            "implementation_date": "2024-07-01",
            "publish_date": "2024-01-15",
            "responsible_dept": "全国标准化技术委员会",
            "abolition_date": "",
            "is_adopted": False,
            "hcno": "mock_gb_001",
            "is_downloadable": True,
        },
        {
            # 模拟风格：接口直返，有，数据库标准不可下载
            "standard_number": "DB11/T 678-2023",
            "standard_name": "北京市 数据安全管理规范",
            "status": "现行",
            "replaces": "DB11/T 678-2019",
            "implementation_date": "2023-10-01",
            "publish_date": "2023-07-20",
            "responsible_dept": "北京市市场监督管理局",
            "abolition_date": "",
            "is_adopted": False,
            "hcno": "mock_db_002",
            "is_downloadable": False,
        },
        {
            # 模拟365风格：有，有
            "standard_number": "DB32/T 4567-2024",
            "standard_name": "江苏省 政务服务数据共享规范",
            "status": "现行",
            "replaces": "DB32/T 4567-2021",
            "implementation_date": "2024-03-01",
            "publish_date": "2024-01-10",
            "responsible_dept": "江苏省市场监督管理局",
            "abolition_date": "",
            "is_adopted": False,
            "hcno": "mock_nj_003",
            "is_downloadable": True,
        },
        {
            # 模拟风格：有_，无，恒可下载
            "standard_number": "DB34/T 8901-2022",
            "standard_name": "安徽省 智慧园区建设指南",
            "status": "现行",
            "replaces": "",
            "implementation_date": "2022-06-01",
            "publish_date": "",
            "responsible_dept": "",
            "abolition_date": "2025-12-31",
            "is_adopted": False,
            "hcno": "",
            "is_downloadable": True,
        },
    ]

    @property
    def site_name(self) -> str:
        return "mock"

    @property
    def site_label(self) -> str:
        return "Mock 数据"

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """按关键词模糊匹配标准号或名称。"""
        term = search_term.lower()
        results: list[QueryResult] = []
        for item in self.MOCK_DATA:
            if term in item["standard_number"].lower() or term in item["standard_name"].lower():
                results.append(
                    QueryResult(
                        standard_number=item["standard_number"],
                        standard_name=item["standard_name"],
                        status=item["status"],
                        replaces=item["replaces"],
                        implementation_date=item["implementation_date"],
                        publish_date=item["publish_date"],
                        responsible_dept=item["responsible_dept"],
                        abolition_date=item["abolition_date"],
                        is_adopted=item["is_adopted"],
                        source_site=self.site_name,
                        hcno=item["hcno"],
                        is_downloadable=item["is_downloadable"],
                    )
                )
        return results
