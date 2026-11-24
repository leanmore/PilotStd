"""分布端点的契约测试（G-43 修复配套，2026-11-24）。

上一提交新增了 `GET /api/notification/logs/stats/distribution`，但漏了
`response_model`（CI 的 `B — API response_model 全覆盖` 步骤抓出）。
本文件锁住该端点的**契约**，防止再次漏声明。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import docker.api.notification_logs as logs_api  # noqa: E402


def test_distribution_endpoint_declares_response_model():
    """端点必须声明 `response_model`（CI 的 B 步骤要求）。

    漏声明会让 FastAPI 不按模型过滤字段，且 `test_api_contract_coverage`
    会把该路由列为违规。
    """
    from fastapi.routing import APIRoute

    target = "/api/notification/logs/stats/distribution"
    route = next(
        (r for r in logs_api.router.routes if isinstance(r, APIRoute) and r.path == target),
        None,
    )
    assert route is not None, f"找不到路由 {target}"
    assert route.response_model is not None, f"{target} 缺少 response_model"
    assert route.response_model is logs_api.LevelDistributionResponse


def test_distribution_response_model_fields():
    """响应模型字段与端点实际返回的键一致。"""
    fields = set(logs_api.LevelDistributionResponse.model_fields)
    assert fields == {"days", "total", "by_level", "by_event_type", "level_rule"}


def test_distribution_payload_matches_model():
    """端点返回的字典键集 == 模型字段集（防止模型与实际返回漂移）。"""
    nmgr = MagicMock()
    nmgr.ops._db.fetchall.return_value = [{"event_type": "task_completed"}]

    result = logs_api.get_log_level_distribution.__wrapped__(
        request=MagicMock(), days=7, nmgr=nmgr
    )
    assert set(result) == set(logs_api.LevelDistributionResponse.model_fields)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
