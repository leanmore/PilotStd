
"""csres 状态文案：只有 is_found() 才是“找到”。"""

from pilotstd.query.engine._csres import csres_state_text
from pilotstd.query.models import QueryResult


def test_csres_state_found_requires_is_found():
    found = QueryResult(standard_number="GB 50016-2014", standard_name="建筑防火")
    not_found = QueryResult(standard_number="GB 50016-2014", error_message="未找到匹配结果")
    assert csres_state_text(found) == "找到"
    assert csres_state_text(not_found) == "未找到"
    assert csres_state_text(None) == "未找到"
