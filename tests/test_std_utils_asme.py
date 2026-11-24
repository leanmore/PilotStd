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
from pilotstd.query.search_strategy import match_result


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
