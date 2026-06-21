# tests/test_classify_std_code.py
# 公共标准分类方法测试
import pytest

from pilotstd.core.std_utils import classify_std_code


@pytest.mark.parametrize(
    "code, expected",
    [
        # GB 类
        ("GB", "gb"),
        ("GB/T", "gb"),
        ("GB/Z", "gb"),
        ("GSB", "gb"),
        # 国际标准
        ("ISO", "iso_iec"),
        ("IEC", "iso_iec"),
        # 国外标准
        ("API", "foreign"),
        ("ASME", "foreign"),
        ("ASTM", "foreign"),
        ("BS", "foreign"),
        ("DIN", "foreign"),
        ("EN", "foreign"),
        ("ANSI", "foreign"),
        ("IEEE", "foreign"),  # 回归：IEEE 不应被 IEC startswith 误匹配为 iso_iec
        ("MSS", "foreign"),
        ("UL", "foreign"),
        ("ITU", "foreign"),
        ("AWWA", "foreign"),
        # 地方标准
        ("DB22", "db"),
        ("DB22/T", "db"),
        ("DB65/T", "db"),
        # 团体标准
        ("TCCSAS", "group"),
        ("TZZB", "group"),
        ("TCED", "group"),
        # 企业标准
        ("SG", "enterprise"),
        # 行业标准
        ("SH/T", "industry"),
        ("NB/T", "industry"),
        ("HG/T", "industry"),
        ("JB/T", "industry"),
        ("NBSHT", "industry"),
        ("JBZQ", "industry"),
        ("SHS", "industry"),
        ("SHJ", "industry"),
        # 未知
        ("UNKNOWN_CODE_XYZ", ""),
    ],
)
def test_classify_std_code(code, expected):
    assert classify_std_code(code) == expected, f"{code} 应为 {expected}"


def test_classify_std_code_case_insensitive():
    """代号大小写不敏感"""
    assert classify_std_code("gb/t") == "gb"
    assert classify_std_code("api") == "foreign"
    assert classify_std_code("iso") == "iso_iec"
    assert classify_std_code("sh/t") == "industry"


def test_classify_std_code_empty():
    """空字符串返回空"""
    assert classify_std_code("") == ""
