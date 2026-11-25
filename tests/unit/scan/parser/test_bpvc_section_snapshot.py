"""ASME BPVC「Section / Div(ision) / Part 册篇字母」扫描侧回归（P1-7.1 B-5）。

已查阅 `docs/plans/2026-11-24-p1-api-asme-gap.md` §2.2 行 13~20 / §3.2 类型 B3 / §4 G2：
修复前 `_ASME_BPVC_RE`（`pilotstd/scan/parser/_constants.py`）只认
`ASME [BPVC.]罗马[-分册][-年份]`，不含 `Section` / `Div(ision)` / `Part 册篇字母`，
导致 `ASME BPVC Section VIII Div. 1-2021` 被通用 exact 通道解析成 `ASME 1-2021`
（把 Div.1 的 1 当序号），`Section II Part D` 直接 MISS。

本文件锁死扫描侧（B 通道）修复后的字段口径，并回归既有 BPVC 通道与普通 ASME 编号。
"""

import pytest

from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser


@pytest.fixture(scope="module")
def parser():
    return StandardParser(build_code_mapping())


class TestBpvcSectionForms:
    """`ASME BPVC Section <卷> Div(ision) <分册>` / `<卷> Part <册篇字母>` 必须解析到正确字段。"""

    @pytest.mark.parametrize(
        "filename, number, part, num_suffix, year",
        [
            ("ASME BPVC Section VIII Div.1-2021.pdf", 8, 1, "", 2021),
            ("ASME BPVC Section VIII Div. 1-2021.pdf", 8, 1, "", 2021),
            ("ASME BPVC Section VIII, Division 1-2021.pdf", 8, 1, "", 2021),
            ("ASME BPVC Section VIII Division 1-2021.pdf", 8, 1, "", 2021),
            ("ASME BPVC Section II Part D-2021.pdf", 2, None, "D", 2021),
            ("ASME BPVC.II.D.M-2021.pdf", 2, None, "D.M", 2021),
            ("ASME BPVC.II.D-2021.pdf", 2, None, "D", 2021),
        ],
    )
    def test_section_and_book_letters(self, parser, filename, number, part, num_suffix, year):
        info = parser.parse(filename)
        assert info is not None, f"{filename} 应能解析"
        assert info.logical_code == "ASME"
        assert info.number == number
        assert info.part == part
        assert info.num_suffix == num_suffix
        assert info.year == year

    @pytest.mark.parametrize(
        "filename, number, part, year, num_prefix",
        [
            ("ASME BPVC.VIII.1-2021.pdf", 8, 1, 2021, "VIII"),
            ("ASME BPVC.VIII-1-2021.pdf", 8, 1, 2021, "VIII"),
            ("ASME BPVC.IX-2021.pdf", 9, None, 2021, "IX"),
        ],
    )
    def test_existing_bpvc_forms_unchanged(self, parser, filename, number, part, year, num_prefix):
        info = parser.parse(filename)
        assert info is not None, f"{filename} 应能解析"
        assert info.logical_code == "ASME"
        assert info.number == number
        assert info.part == part
        assert info.num_prefix == num_prefix
        assert info.year == year

    def test_div_number_not_taken_as_order_number(self, parser):
        """回归报告 §2.2 行 13 的错位：修复前 `Section VIII Div. 1-2021` → ASME number=1。"""
        info = parser.parse("ASME BPVC Section VIII Div. 1-2021.pdf")
        assert info is not None
        assert info.number == 8, "Div.1 的分册号不得抢占卷号"
        assert info.part == 1


class TestNonBpvcAsmeUnaffected:
    """不得回归：普通 ASME 分类字母系列 / 无年份拒绝 / 非 BPVC 的罗马数字形态。"""

    def test_b16_5_with_year(self, parser):
        info = parser.parse("ASME B16.5-2021.pdf")
        assert info is not None
        assert info.logical_code == "ASME"
        assert info.number == 16
        assert info.part == 5
        assert info.year == 2021

    def test_b16_5_without_year_accepted(self, parser):
        """无年份自批次10（P1-7.1 B-7）起合法：国外标准 `year=0`（附录一 §5.4 口径）。

        修复前本用例断言 `is None`（当时无年份放开属 G5，不在 B-5 范围）；批次10 已放开
        `_result_builder.validate_result` 对国外/国际代号的年份硬门，故同批更新为解析成功。
        """
        info = parser.parse("ASME B16.5.pdf")
        assert info is not None
        assert info.logical_code == "ASME"
        assert info.number == 16
        assert info.part == 5
        assert info.year == 0

    def test_plain_roman_volume(self, parser):
        info = parser.parse("ASME VIII.1-2021 压力容器建造规则（中）.pdf")
        assert info is not None
        assert info.number == 8
        assert info.part == 1
        assert info.year == 2021

    def test_non_bpvc_numeric_asme(self, parser):
        """`ASME 1-2021` 不是 BPVC，仍走通用精确通道。"""
        info = parser.parse("ASME 1-2021 压力容器.pdf")
        assert info is not None
        assert info.logical_code == "ASME"
        assert info.number == 1
        assert info.year == 2021
