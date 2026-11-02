"""B/E 组护栏：路由 response_model 全覆盖 + 前端 interface 字段 ⊆ 响应模型。"""

from scripts.check_response_model_coverage import missing_response_models


def test_all_api_routes_have_response_model():
    assert missing_response_models() == []
