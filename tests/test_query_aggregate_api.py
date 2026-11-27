"""聚合端点 API 层测试（GET 纯读语义 + 默认关闭 409 + 开启后返回聚合结果）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api import query_aggregate
from pilotstd.query.aggregation import CONFIG_ENABLED, CONFIG_PER_SITE_TIMEOUT, CONFIG_TOTAL_BUDGET
from pilotstd.query.models import QueryResult


class _Cfg:
    """最小配置桩：启用聚合（测试只验证端点链路，不联网）。"""

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    def get(self, key: str, default: object = None) -> object:
        if key == CONFIG_ENABLED:
            return self._enabled
        if key == CONFIG_PER_SITE_TIMEOUT:
            return 2.0
        if key == CONFIG_TOTAL_BUDGET:
            return 3.0
        return default


class _Adapter:
    """假适配器：固定返回一条标准。"""

    @property
    def site_name(self) -> str:
        return "fake_site"

    def _search_candidates(self, term: str) -> list[QueryResult]:
        return [QueryResult(standard_number="GB/T 1.1-2020", standard_name="导则", status="现行")]


class _Engine:
    """假查询引擎：只提供一个站点与适配器。"""

    def get_all_sites(self) -> list[str]:
        return ["fake_site"]

    def get_adapter(self, site: str):
        return _Adapter() if site == "fake_site" else None


def _client(enabled: bool) -> TestClient:
    app = FastAPI()
    app.include_router(query_aggregate.router)
    mgr = SimpleNamespace(query_engine=_Engine(), cfg=_Cfg(enabled))
    app.dependency_overrides[query_aggregate.get_manager_dep] = lambda: mgr
    return TestClient(app)


class TestAggregateEndpoint:
    def test_disabled_returns_409_without_network(self) -> None:
        client = _client(enabled=False)
        resp = client.get("/api/query/aggregate", params={"query": "GB/T 1.1-2020"})
        assert resp.status_code == 409
        assert "aggregate disabled" in resp.json()["error"]

    def test_enabled_returns_payload_with_site_summaries(self) -> None:
        """启用后返回 200 + 逐站摘要（真实路由选出的站点没有装配适配器 ⇒ 逐站 unavailable）。

        聚合结果条目由服务层测试覆盖（假适配器）；本用例只验证**端点链路**：开关、路由选站、逐站摘要、
        不因未装配站点而 500（失败隔离）。
        """
        client = _client(enabled=True)
        resp = client.get("/api/query/aggregate", params={"query": "GB/T 1.1-2020", "max_sites": 2})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["enabled"] is True
        assert payload["items"] == [] or isinstance(payload["items"], list)
        assert len(payload["sites"]) >= 1
        assert all("site" in site for site in payload["sites"])

    def test_missing_query_returns_422(self) -> None:
        client = _client(enabled=True)
        assert client.get("/api/query/aggregate").status_code == 422


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
