# tests/unit/scan/parser/test_no_year_and_series.py — 批次10（P1-7.1 B-7/B-8/B-9/B-10）B 通道
"""B 通道 `StandardParser.parse` 的无年份放开 + 多字母后缀 + ASME 系列 + 版次修复。

已查阅：
- `docs/plans/2026-11-25-p1-api-refresh.md` §2 逐条矩阵 × §3.1 F2/F3/F4/F5
- `docs/plans/2026-11-24-p1-api-asme-gap.md` §3.2（A1 无年份 / B4 系列前缀 / B5 版次当年份 / B6 后缀截断）
- `docs/reference/附录一 标准代号完整清单.md` §5.4「无年份 → year=0」口径

修复前（2026-11-25 实测）：
- `_result_builder.validate_result` 的 year>0 硬门 → `API STD 610` / `ASME B16.5` / BPVC 无年份全 MISS；
- `_NUM` 只允许 1 个尾字母 → `5CT`→`C`、`2A-WSD`→`A`、`938-C` 直接 MISS；
- `regex_typed` 的 `_YEAR_LOOSE` 把 `11th` 当两位年份 → `year=2011`；
- ASME 的 PTC/CSD 系列词无 handler（B 侧 `num_prefix` 丢）。
"""

import pytest

from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser


@pytest.fixture(scope="module")
def parser():
    return StandardParser(build_code_mapping())


class TestNoYearAccepted:
    """国外/国际标准无年份不得直接判 MISS（year=0 是合法产物）。"""

    @pytest.mark.parametrize(
        "filename, code, number, part, year, num_prefix, num_suffix",
        [
            # 16 条任务样本
            ("API STD 610.pdf", "API", 610, None, 0, "STD", ""),
            ("API RP 2A-WSD.pdf", "API", 2, None, 0, "RP", "A-WSD"),
            ("API TR 938-C.pdf", "API", 938, None, 0, "TR", "C"),
            ("API 579-1.pdf", "API", 579, 1, 0, "", ""),
            ("API 579-1/ASME FFS-1.pdf", "API", 579, 1, 0, "", ""),
            ("ASME B16.5.pdf", "ASME", 16, 5, 0, "B", ""),
            ("ASME BPVC Section II Part D.pdf", "ASME", 2, None, 0, "II", "D"),
            ("ASME BPVC.II.D.pdf", "ASME", 2, None, 0, "II", "D"),
            ("ASME BPVC Section VIII Div.1.pdf", "ASME", 8, 1, 0, "VIII", ""),
            ("ASME BPVC.VIII.1.pdf", "ASME", 8, 1, 0, "VIII", ""),
            # 40 条历史样本
            ("API Spec 5L.pdf", "API", 5, None, 0, "Spec", "L"),
            ("API Q1.pdf", "API", 1, None, 0, "Q", ""),
            ("API MPMS 11.1.pdf", "API", 11, 1, 0, "MPMS", ""),
            ("ASME PTC 4.pdf", "ASME", 4, None, 0, "PTC", ""),
            ("ASME C1.pdf", "ASME", 1, None, 0, "C", ""),
            ("ASME CSD-1.pdf", "ASME", 1, None, 0, "CSD", ""),
        ],
    )
    def test_no_year_fields(self, parser, filename, code, number, part, year, num_prefix, num_suffix):
        info = parser.parse(filename)
        assert info is not None, f"{filename} 无年份不应再判 MISS"
        assert info.logical_code == code
        assert info.number == number
        assert info.part == part
        assert info.year == year
        assert info.num_prefix == num_prefix
        assert info.num_suffix == num_suffix


class TestSuffixAndAsmeSeries:
    """多字母/连字符后缀与 ASME 系列词必须落 `num_suffix` / `num_prefix`。"""

    @pytest.mark.parametrize(
        "filename, code, number, year, num_prefix, num_suffix",
        [
            ("API Spec 5CT-2018.pdf", "API", 5, 2018, "Spec", "CT"),
            ("API RP 2A-WSD.pdf", "API", 2, 0, "RP", "A-WSD"),
            ("API TR 938-C.pdf", "API", 938, 0, "TR", "C"),
            ("API 6D-2021.pdf", "API", 6, 2021, "", "D"),
            # 16 条任务样本 14/15：ASME 系列词不得丢（修复前 num_prefix 为空）
            ("ASME PTC 4-2013.pdf", "ASME", 4, 2013, "PTC", ""),
            ("ASME CSD-1-2024.pdf", "ASME", 1, 2024, "CSD", ""),
            # 16 条任务样本 16：联合标准 + 三级编号
            ("ASME A112.18.1/CSA B125.1.pdf", "ASME", 112, 0, "A", ".1"),
        ],
    )
    def test_suffix_and_series(self, parser, filename, code, number, year, num_prefix, num_suffix):
        info = parser.parse(filename)
        assert info is not None, f"{filename} 应能解析"
        assert info.logical_code == code
        assert info.number == number
        assert info.year == year
        assert info.num_prefix == num_prefix
        assert info.num_suffix == num_suffix


class TestEditionNotYear:
    """`11th` / `11th Edition` 是版次，不得被 `_YEAR_LOOSE` 当成两位年份（2021→2011）。"""

    @pytest.mark.parametrize(
        "filename, number",
        [
            ("API 610-11th.pdf", 610),
            ("API STD 610-11th Edition.pdf", 610),
        ],
    )
    def test_edition_year_is_zero(self, parser, filename, number):
        info = parser.parse(filename)
        assert info is not None, f"{filename} 应能解析"
        assert info.number == number
        assert info.year == 0, f"{filename} 版次被当年份：year={info.year}"


class TestExistingWithYearUnaffected:
    """带年份的既有形态不得回归。"""

    @pytest.mark.parametrize(
        "filename, code, number, part, year, num_prefix",
        [
            ("API 610-2004.pdf", "API", 610, None, 2004, ""),
            ("ASME B16.5-2020.pdf", "ASME", 16, 5, 2020, "B"),
            ("ASME Y14.5-2018.pdf", "ASME", 14, 5, 2018, "Y"),
            ("ASME BPVC.VIII.1-2025.pdf", "ASME", 8, 1, 2025, "VIII"),
            ("ASME BPVC Section VIII Div.1-2021.pdf", "ASME", 8, 1, 2021, "VIII"),
        ],
    )
    def test_with_year(self, parser, filename, code, number, part, year, num_prefix):
        info = parser.parse(filename)
        assert info is not None, f"{filename} 应能解析"
        assert info.logical_code == code
        assert info.number == number
        assert info.part == part
        assert info.year == year
        assert info.num_prefix == num_prefix
