"""Round-trip 测试：make_standard_filename(x) → parse() 往返一致性。

覆盖 DB（推荐/强制）、行业、国标、团体标准；DB 各输入变体统一为无空格形态。
"""

import pytest

from pilotstd.core.file_utils import make_standard_filename
from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser

parser = StandardParser(build_code_mapping())


@pytest.mark.parametrize(
    "logical_code,number,year,std_name",
    [
        # DB 推荐性（无空格形态）
        ("DB22/T", 2883, 2018, "某地标"),
        ("DB65/T", 4567, 2023, "某地标"),
        # DB 强制性
        ("DB50", 1982, 2026, "畜禽粪肥"),
        # 行标
        ("NB/T", 47008, 2010, "承压设备"),
        ("SH/T", 3518, 2025, "石油化工"),
        ("HG/T", 2457, 2006, "化工标准"),
        # 国标
        ("GB/T", 12345, 2020, "国家标准"),
        # 团体标准（透传模式下任意组织代码均可）
        ("T/CIESC", 1, 2019, "某团标"),
    ],
)
def test_roundtrip(logical_code, number, year, std_name):
    filename = make_standard_filename(logical_code, number, year, std_name)
    assert "/" not in filename, f"文件名含斜杠: {filename}"
    parsed = parser.parse(filename)
    assert parsed is not None, f"解析失败: {filename}"
    assert parsed.logical_code == logical_code, (
        f"logical_code 不匹配: {parsed.logical_code!r} != {logical_code!r}"
    )
    assert parsed.number == number
    assert parsed.year == year


def test_roundtrip_db_variants():
    """验证 DB 各种输入变体解析后统一为无空格形态。"""
    for variant in ["DB22/T 2883-2018", "DB 22T 2883-2018", "DB22T 2883-2018"]:
        parsed = parser.parse(variant + " 某地标.pdf")
        assert parsed is not None, f"解析失败: {variant}"
        assert parsed.logical_code == "DB22/T", (
            f"变体 {variant!r} → {parsed.logical_code!r}"
        )


def test_roundtrip_group_variants():
    """团体标准带/无斜杠输入统一解析为 T/XXX。"""
    for variant in ["T/CIESC 001-2019 某团标.pdf", "TCIESC 001-2019 某团标.pdf"]:
        parsed = parser.parse(variant)
        assert parsed is not None, f"解析失败: {variant}"
        assert parsed.logical_code == "T/CIESC"
        assert parsed.number == 1
        assert parsed.year == 2019
