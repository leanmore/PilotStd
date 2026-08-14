"""base.py 适配器测试公共夹具。

提供 make_query_result 工厂，确保 is_found() 的隐式依赖字段默认填充，
避免逐个测试重复构造时遗漏 standard_name 导致 is_found() → False。
"""

import pytest

from pilotstd.query.models import QueryResult


@pytest.fixture
def make_query_result():
    """QueryResult 工厂：默认填充 is_found() 依赖的所有必要字段。

    is_found() 要求 bool(self.standard_name) and not self.error_message，
    因此 standard_name 和 error_message 必须正确设置才能通过检查。
    """

    def _make(**overrides):
        defaults = {
            "standard_number": "GB/T 1234-2020",
            "standard_name": "Test Standard",
            "source_site": "test_site",
            "error_message": "",
        }
        defaults.update(overrides)
        return QueryResult(**defaults)

    return _make
