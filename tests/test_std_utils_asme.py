"""ASME 分类字母系列（B / Y / C）编号解析回归。

背景（已查阅 `docs/plans/2026-11-24-p1-api-asme-gap.md` §2.2 实测表 / §3.2 类型 B1 / §4 G1）：
`parse_std_number("ASME B16.5-2020")` 曾把 `ASME B16` 当成代号、把 `6.5` 当成序号，
返回 `code=ASMEB1 / number=6 / part=5`；`ASME B16.5`、`ASME B31.3`、`ASME Y14.5` 直接
识别不出。后果是 `match_result("ASME", 16, 2020, ..., "ASME B16.5-2020")` 把**同一编号
与自身**比对判成 `mismatch`（score 0）。

本文件锁死修复后的字段口径，并回归「不得波及」的既有编号族。
"""

import pytest

from pilotstd.core.std_utils import parse_std_number
from pilotstd.query.search_strategy import _strip_code_noise, match_result


class TestAsmeLetterSeriesNoSplit:
    """`<代号> <分类字母><序号>[.部分][-年份]` 不得被拆成「代号尾随数字」。"""

    @pytest.mark.parametrize(
        "text, number, part, year",
        [
            # 任务验收的 5 条
            ("ASME B16.5-2020", 16, 5, 2020),
            ("ASME B16.5", 16, 5, 0),
            ("ASME B31.3", 31, 3, 0),
            ("ASME Y14.5", 14, 5, 0),
            ("ASME B1.1-2019", 1, 1, 2019),
            # 报告 §2.2 同族实测样本
            ("ASME B16.34-2017", 16, 34, 2017),
            ("ASME B31.1-2020", 31, 1, 2020),
            ("ASME Y14.5-2018", 14, 5, 2018),
        ],
    )
    def test_code_number_part_year(self, text, number, part, year):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == "ASME"
        assert r["raw_code"] == "ASME"
        assert r["number"] == number
        assert r["part"] == part
        assert r["year"] == year

    def test_class_letter_kept_as_num_prefix(self):
        """B16.5 中的 B 是分类字母（models.ParsedStdInfo.num_prefix 注释口径），不能丢。"""
        assert parse_std_number("ASME B16.5-2020")["num_prefix"] == "B"
        assert parse_std_number("ASME B31.3")["num_prefix"] == "B"
        assert parse_std_number("ASME Y14.5")["num_prefix"] == "Y"


class TestMatchResultSelfCompare:
    """站点返回与本地完全同号时必须 exact —— 修复前是 mismatch（自己和自己比不过）。"""

    @pytest.mark.parametrize(
        "local_code, local_number, local_year, result_number_str",
        [
            ("ASME", 16, 2020, "ASME B16.5-2020"),
            ("ASME", 31, 2020, "ASME B31.3-2020"),
            ("ASME", 14, 2018, "ASME Y14.5-2018"),
            ("ASME", 1, 2019, "ASME B1.1-2019"),
        ],
    )
    def test_same_number_is_exact(self, local_code, local_number, local_year, result_number_str):
        ok, status = match_result(local_code, local_number, local_year, "", result_number_str)
        assert (ok, status) == (True, "exact"), f"{result_number_str} -> {(ok, status)}"


class TestExistingFamiliesUnaffected:
    """不得回归：任务点名的 3 条 + 同分支既有编号族 + 罗马数字 ASME 通道。"""

    @pytest.mark.parametrize(
        "text, code, number, part, year",
        [
            ("GB/T 1-2020", "GBT", 1, None, 2020),
            ("JB/T 2-2010", "JBT", 2, None, 2010),
            ("API 610-2004", "API", 610, None, 2004),
            # 同走 parse_std_number 的既有编号族
            ("DB52T 1078-2026", "DB52T", 1078, None, 2026),
            ("NB/SH/T 0001-2026", "NBSHT", 1, None, 2026),
            ("SJ/T-12117-2026", "SJT", 12117, None, 2026),
            ("QB T 1750-2026", "QBT", 1750, None, 2026),
            # ASME 罗马数字卷号仍走 roman 分支（不受字母系列影响）
            ("ASME VIII.1-2021", "ASME", 8, 1, 2021),
        ],
    )
    def test_existing_parse_unchanged(self, text, code, number, part, year):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == code
        assert r["number"] == number
        assert r["part"] == part
        assert r["year"] == year

    def test_unparseable_still_none(self):
        assert parse_std_number("@@@###") is None


class TestAsmeBpvcVolumeForms:
    """B-5：ASME BPVC 卷/册/篇体系（官方点号写法 + Section/Div/Part 写法）。

    已查阅 `docs/plans/2026-11-24-p1-api-asme-gap.md` §2.2 行 12~20 / §3.2 类型 A2 / §4 G2：
    修复前 `parse_std_number` 对这批写法全 MISS（`ASME BPVC.VIII-1-2021` 还会把卷号并进代号）。
    字段口径按报告 G2 建议：卷号→`number`（阿拉伯值）、Div→`part`、册/篇字母（D/M）→`num_suffix`。
    """

    @pytest.mark.parametrize(
        "text, number, part, year, num_prefix, num_suffix",
        [
            ("ASME BPVC.VIII.1-2021", 8, 1, 2021, "VIII", ""),
            ("ASME BPVC.IX-2021", 9, None, 2021, "IX", ""),
            ("ASME BPVC.II.D", 2, None, 0, "II", "D"),
            ("ASME BPVC.II.D.M-2021", 2, None, 2021, "II", "D.M"),
            ("ASME BPVC VIII-1-2021", 8, 1, 2021, "VIII", ""),
            ("ASME BPVC IX-2021", 9, None, 2021, "IX", ""),
            ("ASME BPVC Section VIII Div.1", 8, 1, 0, "VIII", ""),
            ("ASME BPVC Section VIII Div. 1-2021", 8, 1, 2021, "VIII", ""),
            ("ASME BPVC Section VIII, Division 1-2021", 8, 1, 2021, "VIII", ""),
            ("ASME BPVC Section II Part D", 2, None, 0, "II", "D"),
        ],
    )
    def test_bpvc_forms(self, text, number, part, year, num_prefix, num_suffix):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == "ASME"
        assert r["raw_code"] == "ASME"
        assert r["number"] == number
        assert r["part"] == part
        assert r["year"] == year
        assert r["num_prefix"] == num_prefix
        assert r["num_suffix"] == num_suffix

    @pytest.mark.parametrize(
        "text, number, part, year, num_prefix, num_suffix",
        [
            # 报告 §4 G2 建议的 BPVC 语法在省略 `ASME` 前缀时也应成立
            ("BPVC.IX-2021", 9, None, 2021, "IX", ""),
            ("BPVC.II.D", 2, None, 0, "II", "D"),
            ("Section VIII Div.1", 8, 1, 0, "VIII", ""),
            ("Section II Part D", 2, None, 0, "II", "D"),
        ],
    )
    def test_bpvc_forms_without_asme_prefix(self, text, number, part, year, num_prefix, num_suffix):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == "ASME"
        assert r["number"] == number
        assert r["part"] == part
        assert r["year"] == year
        assert r["num_prefix"] == num_prefix
        assert r["num_suffix"] == num_suffix

    def test_roman_only_form_unchanged(self):
        """不带 BPVC/Section 标记时仍走既有 roman 分支（不引入 num_prefix）。"""
        r = parse_std_number("ASME VIII.1-2021")
        assert r is not None
        assert r["code"] == "ASME"
        assert r["number"] == 8
        assert r["part"] == 1
        assert r["year"] == 2021


class TestBpvcMatchResult:
    """B-5：站点返回 BPVC 写法时，与本地 VIII.1-2021 / II.D.M-2021 必须判 exact。"""

    @pytest.mark.parametrize(
        "local_number, local_year, result_number_str",
        [
            (8, 2021, "ASME BPVC.VIII.1-2021"),
            (8, 2021, "ASME BPVC Section VIII Div.1-2021"),
            (8, 2021, "ASME BPVC Section VIII, Division 1-2021"),
            (2, 2021, "ASME BPVC.II.D.M-2021"),
        ],
    )
    def test_bpvc_result_is_exact(self, local_number, local_year, result_number_str):
        ok, status = match_result("ASME", local_number, local_year, "", result_number_str)
        assert (ok, status) == (True, "exact"), f"{result_number_str} -> {(ok, status)}"


class TestApiTypeWordNotPollutingCode:
    """B-6：API 大写类型词（STD/RP/Q…）不是代号的一部分，不得污染 `code`。

    已查阅报告 §2.1 行 5/6/12 / §3.2 类型 B2 / §4 G3：修复前 `API STD 610-2004` 解析出
    `code=APISTD`、`API RP 520-2020`→`APIRP`、`API Q1-2023`→`APIQ`，导致 `match_result`
    拿污染代号与本地 `API` 比对。类型词应落到 `num_prefix`。
    """

    @pytest.mark.parametrize(
        "text, number, year, num_prefix",
        [
            ("API STD 610-2004", 610, 2004, "STD"),
            ("API RP 520-2020", 520, 2020, "RP"),
            ("API Q1-2023", 1, 2023, "Q"),
            # 任务/报告同时点名无年份写法（无年份在 A 通道允许 year=0）
            ("API STD 610", 610, 0, "STD"),
            ("API Q1", 1, 0, "Q"),
        ],
    )
    def test_type_word_goes_to_num_prefix(self, text, number, year, num_prefix):
        r = parse_std_number(text)
        assert r is not None, f"{text} 应能解析"
        assert r["code"] == "API", f"{text} 代号被污染为 {r['code']!r}"
        assert r["raw_code"] == "API"
        assert r["number"] == number
        assert r["year"] == year
        assert r["num_prefix"] == num_prefix

    def test_lowercase_spec_type_word_kept(self):
        """小写混合类型词 `Spec` 走通用分支时本来就正确，不得被本次改动破坏。"""
        r = parse_std_number("API Spec 610-2004")
        assert r is not None
        assert r["code"] == "API"
        assert r["number"] == 610
        assert r["year"] == 2004
        assert r["num_prefix"] == "Spec"

    def test_plain_api_number_unchanged(self):
        r = parse_std_number("API 610-2004")
        assert r is not None
        assert r["code"] == "API"
        assert r["number"] == 610
        assert r["year"] == 2004
        assert r["num_prefix"] == ""

    @pytest.mark.parametrize(
        "local_number, local_year, result_number_str",
        [
            (610, 2004, "API STD 610-2004"),
            (520, 2020, "API RP 520-2020"),
            (1, 2023, "API Q1-2023"),
            (610, 2004, "API Spec 610-2004"),
            (610, 2004, "API 610-2004"),
        ],
    )
    def test_match_result_exact(self, local_number, local_year, result_number_str):
        ok, status = match_result("API", local_number, local_year, "", result_number_str)
        assert (ok, status) == (True, "exact"), f"{result_number_str} -> {(ok, status)}"


class TestCodeNoiseSuffixes:
    """B-6：`_strip_code_noise` 噪音后缀表补齐 API 类型词（报告 §4 G3 建议）。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("APISTD", "API"),
            ("APIRP", "API"),
            ("APISPEC", "API"),
            ("APIBULL", "API"),
            ("APITR", "API"),
            ("APIMPMS", "API"),
            ("APITDB", "API"),
            ("APIPUBL", "API"),
            ("APISTANDARD", "API"),
            # 不得把真正的短代号剥没（保留 ≥2 字符基础代号）
            ("API", "API"),
            ("ARP", "ARP"),
            ("GBT", "GBT"),
        ],
    )
    def test_strip_code_noise(self, raw, expected):
        assert _strip_code_noise(raw) == expected
