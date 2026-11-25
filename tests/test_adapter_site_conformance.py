"""适配器节点 A2：4 站「解析 → 路由 → 适配器」一致性契约（离线，可在 CI 跑）。

背景（2026-11-25，feat/adapters-phase1）：
- A1（批次 10）修复了 ASME/API 编号解析与表示层；本测试锁定「解析结果 → 路由链」不再回退到错误站点；
- 离线验证：不联网、不依赖生产数据；在线冒烟见 `scripts/smoke_adapters.py --live`。

覆盖 4 站：
  1. API Webstore（`api_webstore`）：API 类型词/多段后缀/联合标准 → 必选 `api_webstore`；
  2. ASME（`asme`）：系列词（PTC/CSD）/BPVC 卷册篇 → 必选 `asme`（不得落 `ahbz`/`njbz365` 兜底）；
  3. 重庆（`cqis`）：DB50/DB50T → 路由链必须包含 `cqis`；
  4. 福建（`fj`）：站点当前 **BLOCKED**（全端口 TCP 超时），不做在线断言；此处只锁定「不得误路由到其它省站」。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pilotstd.core.std_utils import parse_std_number
from pilotstd.query.routing.router_v2 import RoutingService

ROOT = Path(__file__).resolve().parents[1]
_CAP = ROOT / "config" / "site_capabilities.yaml"


@pytest.fixture(scope="module")
def routing() -> RoutingService:
    """模块级共享路由服务（加载一次真实能力模型）。"""
    return RoutingService(str(_CAP))


def _sites(routing: RoutingService, query: str) -> list[str]:
    chain = routing.get_route_chain(query)
    out: list[str] = []
    for site in getattr(chain, "sites", []):
        out.append(getattr(site, "site_name", getattr(site, "site_id", str(site))))
    return out


class TestParsingFeedsRouting:
    """A1 解析质量：这 3 个曾出错的形态必须给出正确字段（否则路由会选错站）。"""

    def test_asme_series_word_not_polluting_code(self) -> None:
        parsed = parse_std_number("ASME PTC 4-2013")
        assert parsed["code"] == "ASME"
        assert parsed["num_prefix"] == "PTC"
        assert parsed["number"] == 4

    def test_asme_csd_series(self) -> None:
        parsed = parse_std_number("ASME CSD-1-2024")
        assert parsed["code"] == "ASME"
        assert parsed["num_prefix"] == "CSD"

    def test_api_part_preserved(self) -> None:
        parsed = parse_std_number("API 579-1/ASME FFS-1")
        assert parsed["code"] == "API"
        assert parsed["number"] == 579
        assert parsed["part"] == 1

    def test_db50_logical_code(self) -> None:
        parsed = parse_std_number("DB50/T 1234-2021")
        assert parsed["code"].startswith("DB50")
        assert parsed["number"] == 1234
        assert parsed["year"] == 2021


class TestRouteChainConformance:
    """路由一致性：4 个站点的代表编号必须命中预期站点。"""

    @pytest.mark.parametrize(
        "query",
        ["API 610-2004", "API SPEC 6D-2021", "API 579-1/ASME FFS-1", "API TR 938-C"],
    )
    def test_api_numbers_route_to_api_webstore(self, routing: RoutingService, query: str) -> None:
        sites = _sites(routing, query)
        assert sites and sites[0] == "api_webstore", f"{query} -> {sites}"

    @pytest.mark.parametrize(
        "query",
        [
            "ASME B16.5-2020",
            "ASME PTC 4-2013",
            "ASME CSD-1-2024",
            "ASME BPVC Section VIII Div.1-2021",
        ],
    )
    def test_asme_numbers_route_to_asme(self, routing: RoutingService, query: str) -> None:
        sites = _sites(routing, query)
        assert sites and sites[0] == "asme", f"{query} -> {sites}"
        # 回归：A1 修复前 ASME PTC/CSD 会被判成外语代号 → 落 ahbz/njbhz365 兜底
        assert "ahbz" not in sites and "njbz365" not in sites, f"{query} 落到了兜底站: {sites}"

    def test_db50_routes_include_cqis(self, routing: RoutingService) -> None:
        sites = _sites(routing, "DB50/T 1234-2021")
        assert "cqis" in sites, f"DB50 未包含重庆站: {sites}"

    def test_national_standard_prefers_national_sites(self, routing: RoutingService) -> None:
        sites = _sites(routing, "GB/T 1.1-2020")
        assert sites and sites[0] in {"std_gov", "csres", "cssn"}, f"GB 路由异常: {sites}"


class TestFujianBlockedDocumented:
    """福建站 BLOCKED 的事实必须留在代码里（防止有人误以为它可用）。"""

    def test_fujian_not_in_default_route_for_db50(self, routing: RoutingService) -> None:
        # 福建站未接入（BLOCKED：220.160.53.32 全端口 TCP 超时），DB50 不应路由到它
        sites = _sites(routing, "DB50/T 1234-2021")
        assert "fj" not in sites and "fujian" not in sites, sites
