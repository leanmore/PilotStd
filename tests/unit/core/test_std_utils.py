"""std_utils.py — 标准号解析/分类全覆盖。

跳过: 无（全部是纯解析逻辑，零 I/O）。
KNOWN LIMITATION: classify_std_code 的 DB 正则要求 2-4 位数字，DB1 无法匹配。
"""

from unittest.mock import patch

import pytest

from pilotstd.core.std_utils import (
    _try_parse_db_standard,
    _try_parse_dot_prefix,
    _try_parse_fallback,
    _try_parse_general_format,
    _try_parse_multi_hyphen,
    _try_parse_roman,
    classify_std_code,
    is_gb_code,
    parse_std_number,
)


class TestIsGbCode:
    def test_gb_code_returns_true(self):
        assert is_gb_code("GB") is True
        assert is_gb_code("GB/T") is True
        assert is_gb_code("GB/Z") is True

    def test_non_gb_code_returns_false(self):
        assert is_gb_code("ISO") is False
        assert is_gb_code("SH/T") is False
        assert is_gb_code("") is False


class TestClassifyStdCode:
    @pytest.fixture(autouse=True)
    def _patch_deps(self):
        with patch(
            "pilotstd.organizer.industry_lookup.build_code_mapping",
            return_value={"AQ": "安全生产", "YD": "通信", "SH": "石油化工"},
        ), patch(
            "pilotstd.scan.parser.FOREIGN_CODE_SET",
            {"ASTM", "ASME", "API", "DIN", "BS", "ANSI"},
        ), patch(
            "pilotstd.scan.parser.ISO_IEC_SET",
            {"ISO", "IEC", "ISO/IEC"},
        ):
            yield

    def test_empty_returns_empty(self):
        assert classify_std_code("") == ""

    def test_gb_variants(self):
        assert classify_std_code("GB") == "gb"
        assert classify_std_code("GB/T") == "gb"
        assert classify_std_code("GB/Z") == "gb"

    def test_foreign_code(self):
        assert classify_std_code("ASTM") == "foreign"
        assert classify_std_code("DIN") == "foreign"

    def test_iso_iec(self):
        assert classify_std_code("ISO") == "iso_iec"
        assert classify_std_code("IEC") == "iso_iec"

    def test_db_code(self):
        assert classify_std_code("DB35") == "db"
        assert classify_std_code("DB35/T") == "db"

    def test_enterprise(self):
        assert classify_std_code("SG") == "enterprise"

    def test_industry_in_mapping(self):
        assert classify_std_code("AQ") == "industry"
        assert classify_std_code("SH") == "industry"

    def test_group_code(self):
        assert classify_std_code("T/CPCA") == "group"

    def test_unknown_returns_empty(self):
        assert classify_std_code("UNKNOWN_XY") == ""


class TestParseDbStandard:
    def test_standard_db_format(self):
        r = _try_parse_db_standard("DB35/T 1234-2020")
        assert r["code"] == "DB35T"
        assert r["number"] == 1234
        assert r["year"] == 2020

    def test_db_with_part(self):
        r = _try_parse_db_standard("DB11 456.1-2023")
        assert r["number"] == 456
        assert r["part"] == 1
        assert r["year"] == 2023

    def test_non_db_returns_none(self):
        assert _try_parse_db_standard("GB/T 1234-2020") is None


class TestParseGeneralFormat:
    def test_standard_format(self):
        r = _try_parse_general_format("GB/T 22101-2026")
        assert r["code"] == "GBT"
        assert r["number"] == 22101
        assert r["year"] == 2026

    def test_with_part_number(self):
        r = _try_parse_general_format("ISO 9001.2-2015")
        assert r["number"] == 9001
        assert r["part"] == 2

    def test_invalid_returns_none(self):
        assert _try_parse_general_format("not a standard") is None


class TestParseRoman:
    def test_roman_numeral(self):
        r = _try_parse_roman("ASME VIII.1-2021")
        assert r is not None
        assert r["year"] == 2021

    def test_invalid_returns_none(self):
        assert _try_parse_roman("GB/T 1234-2020") is None


class TestParseDotPrefix:
    def test_dot_prefix_format(self):
        r = _try_parse_dot_prefix("ANSI C.81-2003")
        assert r is not None
        assert r["number"] == 81
        assert r["num_prefix"] == "C"

    def test_invalid_returns_none(self):
        assert _try_parse_dot_prefix("GB/T 1234") is None


class TestParseMultiHyphen:
    def test_multi_hyphen(self):
        r = _try_parse_multi_hyphen("IEC 61000-4-2-2008")
        assert r is not None
        assert r["year"] == 2008

    def test_invalid_returns_none(self):
        assert _try_parse_multi_hyphen("hello") is None


class TestParseFallback:
    def test_code_and_number(self):
        r = _try_parse_fallback("UL 982")
        assert r["code"] == "UL"
        assert r["number"] == 982
        assert r["year"] == 0

    def test_invalid_returns_none(self):
        assert _try_parse_fallback("xyz") is None


class TestParseStdNumber:
    def test_full_format(self):
        r = parse_std_number("GB/T 22101.1-2026")
        assert r["code"] == "GBT"
        assert r["number"] == 22101
        assert r["part"] == 1
        assert r["year"] == 2026

    def test_iso_format(self):
        r = parse_std_number("ISO 9001:2015")
        assert r is not None
        assert r["year"] == 2015

    def test_empty_returns_none(self):
        assert parse_std_number("") is None

    def test_none_returns_none(self):
        assert parse_std_number(None) is None

    def test_unparseable_returns_none(self):
        assert parse_std_number("@@@###") is None

    def test_whitespace_only_returns_none(self):
        assert parse_std_number("   ") is None

    def test_db_standard(self):
        r = parse_std_number("DB35/T 1234-2020")
        assert r is not None
        assert r["code"] == "DB35T"

    def test_roman_numeral(self):
        r = parse_std_number("ASME VIII.1-2021")
        assert r is not None
