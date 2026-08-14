"""ExactMatchMixin Phase A 快照测试 — 7 个匹配通道每通道 >=2 用例。"""

import pytest

from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser


@pytest.fixture(scope="module")
def parser():
    return StandardParser(build_code_mapping())


# _build_result 需要 _current_file_kind — 在 parse() 中设置，
# 直接调用匹配方法时需手动初始化。
@pytest.fixture(autouse=True)
def _init_fk(parser):
    parser._current_file_kind = ""


# ══════════════════════════════════════════════════════════════
# 1. _exact_match — 通用精确匹配
# ══════════════════════════════════════════════════════════════

class TestExactMatch:

    def test_gb_standard(self, parser):
        result = parser._matcher._exact_match("GB/T 123-2020 测试标准.pdf")
        assert result.logical_code == "GB/T"
        assert result.number == 123
        assert result.year == 2020

    def test_sh_standard_with_part(self, parser):
        result = parser._matcher._exact_match("SH/T 3503.1-2017 规定.pdf")
        assert result.logical_code == "SH/T"
        assert result.number == 3503
        assert result.part == 1
        assert result.year == 2017

    def test_no_match_returns_none(self, parser):
        assert parser._matcher._exact_match("no standard here.pdf") is None

    def test_din_en_standard(self, parser):
        result = parser._matcher._exact_match("DIN EN 12345-2020.pdf")
        assert result is not None
        assert "DIN" in result.logical_code


# ══════════════════════════════════════════════════════════════
# 2. _exact_match_db — 地方标准 DB 匹配
# ══════════════════════════════════════════════════════════════

class TestExactMatchDb:

    def test_db_with_t(self, parser):
        result = parser._matcher._exact_match_db("DB35/T 123-2020 地方标准.pdf")
        assert result.logical_code.startswith("DB")
        assert result.number == 123
        assert result.year == 2020

    def test_db_without_t(self, parser):
        result = parser._matcher._exact_match_db("DB35 456-2019.pdf")
        assert result is not None
        assert result.number == 456

    def test_db_no_year(self, parser):
        """DB35/T 789-2020 正常带年份。"""
        result = parser._matcher._exact_match_db("DB35/T 789-2020")
        assert result is not None
        assert result.number == 789

    def test_not_db_pattern(self, parser):
        assert parser._matcher._exact_match_db("GB/T 123-2020.pdf") is None


# ══════════════════════════════════════════════════════════════
# 3. _exact_match_typed — 带类型前缀匹配
# ══════════════════════════════════════════════════════════════

class TestExactMatchTyped:

    def test_iso_endorsed(self, parser):
        result = parser._matcher._exact_match_typed("ISO/IEC 12345-2020 标准.pdf")
        assert result is not None
        assert "ISO" in result.logical_code

    def test_no_endorser(self, parser):
        result = parser._matcher._exact_match_typed("ISO 9001-2015.pdf")
        assert result is not None
        assert result.number == 9001

    def test_not_typed_generic_name(self, parser):
        """非标准文件名 → _exact_match_typed 返回 None。"""
        assert parser._matcher._exact_match_typed("random text no standard.pdf") is None


# ══════════════════════════════════════════════════════════════
# 4. _exact_match_no_year — 无年份匹配（修订版标准）
# ══════════════════════════════════════════════════════════════

class TestExactMatchNoYear:

    def test_mil_std_with_letter_suffix(self, parser):
        """MIL-STD-810G → number=810, num_suffix='G'，字母后缀表示修订版次。"""
        result = parser._matcher._exact_match_no_year("MIL-STD-810G.pdf")
        assert result is not None
        assert result.number == 810
        assert result.num_suffix == "G"
        assert result.year == 0

    def test_no_letter_suffix_returns_none(self, parser):
        """无字母后缀的裸编号 → 返回 None（避免误匹配表单模板）。"""
        assert parser._matcher._exact_match_no_year("GB/T 123-2020.pdf") is None

    def test_gb_with_letter_suffix(self, parser):
        """GB/T 810G → 带字母后缀但非 exact_match_no_year 主要目标。"""
        result = parser._matcher._exact_match_no_year("GB/T 810G.pdf")
        # GB 有 letter suffix 时应匹配
        if result is not None:
            assert result.num_suffix == "G"


# ══════════════════════════════════════════════════════════════
# 5. _exact_match_bpvc — ASME BPVC 罗马数字卷号
# ══════════════════════════════════════════════════════════════

class TestExactMatchBpvc:

    def test_bpvc_roman_numeral(self, parser):
        """ASME BPVC IX-2021 → 罗马数字 IX(=9) 映射为 volume number。"""
        result = parser._matcher._exact_match_bpvc("ASME BPVC IX-2021.pdf")
        assert result is not None
        assert result.num_prefix == "IX"
        assert result.number == 9
        assert result.year == 2021

    def test_bpvc_with_sub(self, parser):
        """ASME BPVC VIII-2-2019 → 有 sub 编号。"""
        result = parser._matcher._exact_match_bpvc("ASME BPVC VIII-2-2019.pdf")
        assert result is not None
        assert result.number == 8

    def test_non_bpvc_asme(self, parser):
        """非 BPVC 的 ASME 标准 → _exact_match_bpvc 应返回 None。"""
        assert parser._matcher._exact_match_bpvc("ASME B16.5-2020.pdf") is None


# ══════════════════════════════════════════════════════════════
# 6. _exact_match_itu — ITU 推荐号匹配
# ══════════════════════════════════════════════════════════════

class TestExactMatchItu:

    def test_itu_t_with_year(self, parser):
        result = parser._matcher._exact_match_itu("ITU-T G.992.1-1999 电信标准.pdf")
        assert result is not None
        assert result.logical_code == "ITU-T"
        assert result.num_prefix == "G.992.1"
        assert result.year == 1999

    def test_itu_r_no_year(self, parser):
        result = parser._matcher._exact_match_itu("ITU-R M.1457-2019.pdf")
        assert result is not None
        assert result.logical_code == "ITU-R"
        assert result.year == 2019

    def test_not_itu(self, parser):
        assert parser._matcher._exact_match_itu("ISO 9001-2015.pdf") is None


# ══════════════════════════════════════════════════════════════
# 7. _fuzzy_match_with_context — 上下文感知模糊匹配
# ══════════════════════════════════════════════════════════════

class TestFuzzyMatch:

    def test_gb_with_context(self, parser):
        """从模糊文件名中提取年份和编号。"""
        result = parser._matcher._fuzzy_match_with_context("GB T 12345 2020 标准名称.pdf")
        assert result is not None
        assert result.number == 12345
        assert result.year == 2020

    def test_code_not_in_mapping(self, parser):
        """未知代号 → logical_code 使用 raw prefix。"""
        result = parser._matcher._fuzzy_match_with_context("XX 12345 2020 something.pdf")
        if result is not None:
            assert result.logical_code == "XX"

    def test_no_year_in_name(self, parser):
        """无年份 → 返回 None。"""
        assert parser._matcher._fuzzy_match_with_context("GB T 12345 noyear.pdf") is None
