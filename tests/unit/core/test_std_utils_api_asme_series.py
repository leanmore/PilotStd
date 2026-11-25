# tests/unit/core/test_std_utils_api_asme_series.py — 批次10（P1-7.1 B-8/B-9）A 通道编号解析扩展
"""A 通道 `parse_std_number` 的 API 后缀/联合标准 + ASME 系列词覆盖回归。

已查阅：
- `docs/plans/2026-11-25-p1-api-refresh.md` §2 逐条矩阵（16 条样本）× §3.1 F1/F3/F6
- `docs/plans/2026-11-24-p1-api-asme-gap.md` §3.2 A3/B4/B6 + §4 G6/G7

修复前（2026-11-25 实测）：
- `ASME PTC 4-2013` → `code=ASMEPTC`（类型/系列词污染代号），`match_result("ASME", 4, 2013, ...)` 判 mismatch；
- `API RP 2A-WSD` / `API TR 938-C` / `API 579-1` / `ASME A112.18.1/CSA B125.1` 全部 MISS（无连字符
  多段后缀、无 part、无联合标准与三级编号分支）。
"""

import pytest

from pilotstd.core.std_utils import classify_std_code, parse_std_number
from pilotstd.query.search_strategy import match_result


class TestApiSuffixAndJoint:
    """`API <类型词?> <序号><字母后缀/part><-年份>` 必须拆全字段（含无年份）。"""

    @pytest.mark.parametrize(
        "text, number, part, year, num_prefix, num_suffix",
        [
            # 16 条任务样本中的 4/5/6/7
            ("API RP 2A-WSD", 2, None, 0, "RP", "A-WSD"),
            ("API TR 938-C", 938, None, 0, "TR", "C"),
            ("API 579-1", 579, 1, 0, "", ""),
            ("API 579-1/ASME FFS-1", 579, 1, 0, "", ""),
            # 40 条历史样本中的多字母后缀/无年份
            ("API 6D", 6, None, 0, "", "D"),
            ("API 6D-2021", 6, None, 2021, "", "D"),
            ("API Spec 5CT-2018", 5, None, 2018, "Spec", "CT"),
            ("API Bull 2U", 2, None, 0, "Bull", "U"),
            ("API MPMS 11.1", 11, 1, 0, "MPMS", ""),
            # 版次不得当年份（G4）
            ("API 610-11th", 610, None, 0, "", ""),
            ("API STD 610-11th Edition", 610, None, 0, "STD", ""),
            # 既有基线不得回归
            ("API 610-2004", 610, None, 2004, "", ""),
            ("API SPEC 6D-2021", 6, None, 2021, "SPEC", "D"),
            ("API STD 610", 610, None, 0, "STD", ""),
            ("API Q1", 1, None, 0, "Q", ""),
        ],
    )
    def test_api_forms(self, text, number, part, year, num_prefix, num_suffix):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == "API", f"{text} 代号被污染为 {r['code']!r}"
        assert r["number"] == number
        assert r["part"] == part
        assert r["year"] == year
        assert r["num_prefix"] == num_prefix
        assert r["num_suffix"] == num_suffix


class TestAsmeSeriesWords:
    """ASME 系列词（PTC/CSD）落 `num_prefix`，代号保持 `ASME`（不被并成 `ASMEPTC`）。"""

    @pytest.mark.parametrize(
        "text, number, part, year, num_prefix, num_suffix",
        [
            # 16 条任务样本中的 14/15
            ("ASME PTC 4-2013", 4, None, 2013, "PTC", ""),
            ("ASME CSD-1-2024", 1, None, 2024, "CSD", ""),
            # 40 条历史样本中的无年份写法
            ("ASME PTC 4", 4, None, 0, "PTC", ""),
            ("ASME CSD-1", 1, None, 0, "CSD", ""),
            ("ASME C1", 1, None, 0, "C", ""),
        ],
    )
    def test_asme_series(self, text, number, part, year, num_prefix, num_suffix):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == "ASME", f"{text} 代号被污染为 {r['code']!r}"
        assert r["raw_code"] == "ASME"
        assert r["number"] == number
        assert r["part"] == part
        assert r["year"] == year
        assert r["num_prefix"] == num_prefix
        assert r["num_suffix"] == num_suffix

    def test_asme_letter_series_not_regressed(self):
        """分类字母系列（B/Y/C）口径不变，且不引入 num_suffix。"""
        r = parse_std_number("ASME B16.5-2020")
        assert r is not None
        assert (r["code"], r["number"], r["part"], r["year"], r["num_prefix"]) == ("ASME", 16, 5, 2020, "B")
        assert r["num_suffix"] == ""


class TestAsmeThreeLevelAndJoint:
    """`ASME A112.18.1/CSA B125.1`：联合标准只取主标准，三级编号 `.1` 落 `num_suffix`（报告 §5 口径）。"""

    @pytest.mark.parametrize(
        "text, part, num_suffix",
        [
            ("ASME A112.18.1/CSA B125.1", 18, ".1"),
            ("ASME A112.18.1", 18, ".1"),
        ],
    )
    def test_three_level(self, text, part, num_suffix):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == "ASME"
        assert r["number"] == 112
        assert r["part"] == part
        assert r["year"] == 0
        assert r["num_prefix"] == "A"
        assert r["num_suffix"] == num_suffix


class TestAsmeSeriesCanonicalMatch:
    """修复前同一编号配正确本地记录会判 mismatch；修复后必须 exact（型号口径 §3.1 F1）。"""

    @pytest.mark.parametrize(
        "local_number, local_year, result_number_str",
        [
            (4, 2013, "ASME PTC 4-2013"),
            (1, 2024, "ASME CSD-1-2024"),
            (4, 0, "ASME PTC 4"),
            (1, 0, "ASME CSD-1"),
            (112, 0, "ASME A112.18.1/CSA B125.1"),
            (2, 0, "API RP 2A-WSD"),
            (938, 0, "API TR 938-C"),
            (579, 0, "API 579-1/ASME FFS-1"),
        ],
    )
    def test_match_exact(self, local_number, local_year, result_number_str):
        if result_number_str.startswith("ASME"):
            ok, status = match_result("ASME", local_number, local_year, "", result_number_str)
        else:
            ok, status = match_result("API", local_number, local_year, "", result_number_str)
        assert (ok, status) == (True, "exact"), f"{result_number_str} -> {(ok, status)}"


class TestAsmeSeriesRouting:
    """代号修复后走 `CODE_ROUTES["ASME"]`（asme 站点），不得落到通用国外兜底链。"""

    def test_asme_series_code_classifies_foreign(self):
        code = parse_std_number("ASME PTC 4-2013")["code"]
        assert code == "ASME"
        assert classify_std_code(code) == "foreign"

    def test_asme_route_targets_asme_site(self):
        from pilotstd.query.engine._constants import CODE_ROUTES

        assert CODE_ROUTES["ASME"][0] == "asme"
