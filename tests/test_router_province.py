"""D-2 省份粒度路由测试（用户 2026-11-26 批准方案 b）。

规则：
1. 省级标准代码（`DB50/T` → 重庆）在 L1 精准层**优先本省站**（cqis 排在 dbba 前）；
2. 声明了**其它省份**的站点被排除（DB11 北京查询不出现 cqis）；
3. 未声明 province 的通用库保留兜底（dbba 仍在链上）；
4. 非省级标准（GB/T）与纯关键词查询行为不变。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pilotstd.query.routing.router_v2 import (
    PROVINCE_BY_CODE,
    RoutingService,
    load_capabilities,
    province_of_query,
)

ROOT = Path(__file__).resolve().parents[1]
_CAP = ROOT / "config" / "site_capabilities.yaml"


@pytest.fixture(scope="module")
def routing() -> RoutingService:
    return RoutingService(str(_CAP))


def _sites(routing: RoutingService, query: str) -> list[str]:
    chain = routing.get_route_chain(query)
    return [getattr(s, "site_name", getattr(s, "site_id", str(s))) for s in chain.sites]


class TestProvinceOfQuery:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("DB50/T 1234-2021", "重庆"),
            ("DB50T1234-2021", "重庆"),
            ("db11/t 1000-2020", "北京"),
            ("DB35/T 1-2020", "福建"),
            ("GB/T 1.1-2020", ""),
            ("API 610-2004", ""),
            ("", ""),
        ],
    )
    def test_code_mapping(self, query: str, expected: str) -> None:
        assert province_of_query(query) == expected

    def test_mapping_covers_municipalities_and_provinces(self) -> None:
        assert PROVINCE_BY_CODE["50"] == "重庆"
        assert PROVINCE_BY_CODE["11"] == "北京"
        assert PROVINCE_BY_CODE["35"] == "福建"
        assert len(PROVINCE_BY_CODE) >= 30


class TestCapabilitiesLoader:
    def test_cqis_declares_province(self) -> None:
        caps = {c.site_id: c for c in load_capabilities(str(_CAP))}
        assert caps["cqis"].capabilities.province == "重庆"

    def test_generic_site_has_empty_province(self) -> None:
        caps = {c.site_id: c for c in load_capabilities(str(_CAP))}
        assert caps["hbba"].capabilities.province == ""
        assert caps["dbba"].capabilities.province == ""


class TestProvinceRouting:
    def test_chongqing_standard_prefers_cqis(self, routing: RoutingService) -> None:
        sites = _sites(routing, "DB50/T 1234-2021")
        assert sites[:2] == ["cqis", "dbba"], sites

    def test_other_province_excluded(self, routing: RoutingService) -> None:
        # DB11（北京）：cqis 声明重庆 → 不得命中；dbba 为通用库兜底
        sites = _sites(routing, "DB11/T 1000-2020")
        assert "cqis" not in sites, sites
        assert sites == ["dbba"], sites

    def test_fujian_standard_not_claimed_by_chongqing(self, routing: RoutingService) -> None:
        sites = _sites(routing, "DB35/T 1-2020")
        assert "cqis" not in sites
        assert "dbba" in sites

    def test_decision_mentions_province(self, routing: RoutingService) -> None:
        chain = routing.get_route_chain("DB50/T 1234-2021")
        joined = " ".join(chain.decisions)
        assert "province=重庆" in joined
        assert "province_hit" in joined

    def test_national_standard_unaffected(self, routing: RoutingService) -> None:
        sites = _sites(routing, "GB/T 1.1-2020")
        assert sites[0] in {"std_gov", "csres", "cssn"}, sites

    def test_keyword_query_unaffected(self, routing: RoutingService) -> None:
        sites = _sites(routing, "离心泵")
        assert sites, "关键词查询应有 L3 兜底链"
