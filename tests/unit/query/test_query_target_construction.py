# tests/unit/query/test_query_target_construction.py — 批次10（P1-7.1 B-12）查询 target 构造
"""查询 target 构造 + BPVC 代号变体回归（报告 §3.2 R1）。

已查阅：
- `docs/plans/2026-11-25-p1-api-refresh.md` §3.2 R1（实跑：16 条样本仅 4/16 生成期望
  designator/productcode；BPVC 生成 `ASME VIII8.1-2025`）
- `docs/plans/2026-11-24-p1-api-asme-gap.md` §4 G8（`build_code_variants` 用卷号当分册号）

修复前（2026-11-25 实测）：
- `BaseAdapter.query_with_strategy` 的 target 为 `code prefix+number+suffix+part-year` 直接粘连，
  `year=0` 也追加 `-0`，`num_suffix` 被忽略；
- `build_code_variants("ASME", 8, 2025, "VIII")` → `ASME BPVC VIII.8-2025`（把卷号当分册号）。
"""

import pytest

from pilotstd.query.adapters.api_webstore import ApiWebstoreAdapter
from pilotstd.query.adapters.asme import AsmeAdapter
from pilotstd.query.adapters.base import BaseAdapter
from pilotstd.query.models import QueryResult
from pilotstd.query.search_strategy import build_code_variants


class _CaptureAdapter(BaseAdapter):
    """捕获 `query_with_strategy` 实际生成的搜索词（`_search_candidates` 返回空，无网络）。"""

    def __init__(self) -> None:
        self.terms: list[str] = []

    @property
    def site_name(self) -> str:
        return "capture"

    @property
    def site_label(self) -> str:
        return "capture"

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        self.terms.append(search_term)
        return []


def _first_term(**kwargs) -> str:
    adapter = _CaptureAdapter()
    adapter.query_with_strategy(**kwargs)
    assert adapter.terms, "应至少生成一个搜索词"
    return adapter.terms[0]


class TestTargetConstruction:
    """target 必须是「可被适配器归一化」的标准号写法（空格分隔、BPVC 点号、year=0 不追加）。"""

    @pytest.mark.parametrize(
        "kwargs, expected",
        [
            # ASME 任务样本 8~16
            (
                dict(logical_code="ASME", number=8, year=2025, part=1, num_prefix="VIII"),
                "ASME BPVC.VIII.1-2025",
            ),
            (
                dict(logical_code="ASME", number=2, year=0, num_prefix="II", num_suffix="D"),
                "ASME BPVC.II.D",
            ),
            (dict(logical_code="ASME", number=4, year=2013, num_prefix="PTC"), "ASME PTC 4-2013"),
            (dict(logical_code="ASME", number=1, year=2024, num_prefix="CSD"), "ASME CSD-1-2024"),
            (
                dict(logical_code="ASME", number=112, year=0, part=18, num_prefix="A", num_suffix=".1"),
                "ASME A112.18.1",
            ),
            # API 任务样本 1~7
            (dict(logical_code="API", number=610, year=2004), "API 610-2004"),
            (dict(logical_code="API", number=610, year=0, num_prefix="STD"), "API STD 610"),
            (
                dict(logical_code="API", number=6, year=2021, num_prefix="SPEC", num_suffix="D"),
                "API SPEC 6D-2021",
            ),
            (
                dict(logical_code="API", number=2, year=0, num_prefix="RP", num_suffix="A-WSD"),
                "API RP 2A-WSD",
            ),
            (dict(logical_code="API", number=938, year=0, num_prefix="TR", num_suffix="C"), "API TR 938-C"),
            (dict(logical_code="API", number=579, year=0, part=1), "API 579-1"),
        ],
    )
    def test_first_term(self, kwargs, expected):
        assert _first_term(**kwargs) == expected

    def test_no_year_target_has_no_zero_year(self):
        terms = _CaptureAdapter()
        terms.query_with_strategy(logical_code="API", number=610, year=0, num_prefix="STD")
        assert not any(term.endswith("-0") for term in terms.terms), terms.terms


class TestBpvcVariant:
    """BPVC 变体用卷号+分册号（`VIII.1`），不得再把卷号当分册（`VIII.8`）。"""

    def test_bpvc_variant_uses_part(self):
        variants = build_code_variants("ASME", 8, 2025, "VIII", part=1)
        assert "ASME BPVC.VIII.1-2025" in variants
        assert all("VIII.8" not in v for v in variants), variants

    def test_bpvc_variant_without_part(self):
        variants = build_code_variants("ASME", 9, 2021, "IX")
        assert "ASME BPVC.IX-2021" in variants
        assert all("IX.9" not in v for v in variants), variants

    def test_api_and_din_variants_unchanged(self):
        api = build_code_variants("API", 610, 2004)
        assert api == ["API Std 610-2004", "API Spec 610-2004"]
        din = build_code_variants("DIN", 1092, 2018)
        assert din == ["DIN EN 1092-2018"]


class TestRouteCodeNormalization:
    """item 1：ASME 系列词污染代号不得落 `_FOREIGN_FALLBACK`（应走 asme 站点）。"""

    def test_asme_series_codes_normalized(self):
        from pilotstd.query.engine._constants import _FOREIGN_FALLBACK, CODE_ROUTES, normalize_route_code

        for dirty in ("ASMEPTC", "ASMECSD", "ASME PTC", "ASME CSD"):
            assert normalize_route_code(dirty) == "ASME", dirty
        # 归一化后命中专业路由，而不是通用国外兜底链
        assert CODE_ROUTES["ASME"][0] == "asme"
        assert "asme" not in _FOREIGN_FALLBACK

    def test_other_codes_unchanged(self):
        from pilotstd.query.engine._constants import normalize_route_code

        for code in ("API", "GB/T", "ASTM", "ISO", ""):
            assert normalize_route_code(code) == code


class TestExpectedDesignatorHit:
    """16 条样本中 ASME/API 的 target 归一化后必须命中期望 designator/productcode。"""

    @pytest.mark.parametrize(
        "expected_text, kwargs",
        [
            ("ASME B16.5-2020", dict(logical_code="ASME", number=16, year=2020, part=5, num_prefix="B")),
            ("ASME B31.3-2024", dict(logical_code="ASME", number=31, year=2024, part=3, num_prefix="B")),
            ("ASME Y14.5-2018", dict(logical_code="ASME", number=14, year=2018, part=5, num_prefix="Y")),
            (
                "ASME BPVC.VIII.1-2025",
                dict(logical_code="ASME", number=8, year=2025, part=1, num_prefix="VIII"),
            ),
            (
                "ASME BPVC Section VIII Div.1-2021",
                dict(logical_code="ASME", number=8, year=2021, part=1, num_prefix="VIII"),
            ),
            (
                "ASME BPVC Section II Part D",
                dict(logical_code="ASME", number=2, year=0, num_prefix="II", num_suffix="D"),
            ),
            ("ASME PTC 4-2013", dict(logical_code="ASME", number=4, year=2013, num_prefix="PTC")),
            ("ASME CSD-1-2024", dict(logical_code="ASME", number=1, year=2024, num_prefix="CSD")),
            ("API 610-2004", dict(logical_code="API", number=610, year=2004)),
            ("API STD 610", dict(logical_code="API", number=610, year=0, num_prefix="STD")),
            (
                "API SPEC 6D-2021",
                dict(logical_code="API", number=6, year=2021, num_prefix="SPEC", num_suffix="D"),
            ),
            (
                "API RP 2A-WSD",
                dict(logical_code="API", number=2, year=0, num_prefix="RP", num_suffix="A-WSD"),
            ),
            ("API TR 938-C", dict(logical_code="API", number=938, year=0, num_prefix="TR", num_suffix="C")),
            ("API 579-1", dict(logical_code="API", number=579, year=0, part=1)),
        ],
    )
    def test_designator_or_productcode_hit(self, expected_text, kwargs):
        term = _first_term(**kwargs)
        if expected_text.startswith("ASME"):
            assert AsmeAdapter._normalize_designator(term) == AsmeAdapter._normalize_designator(expected_text)
        else:
            assert ApiWebstoreAdapter._extract_productcode(term) == ApiWebstoreAdapter._extract_productcode(
                expected_text
            )
