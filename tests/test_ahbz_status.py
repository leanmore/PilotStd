# tests/test_ahbz_status.py
# ahbz 适配器 status 映射 + 结构化比对测试
import pytest
from pilotstd.query.adapters import ahbz


def test_status_map_active_means_current():
    """ahbz 返回 status='A' 应映射为'现行'（非'废止'）"""
    assert ahbz._STATUS_MAP.get("A") == "现行", f"A 应为现行，实际: {ahbz._STATUS_MAP.get('A')}"


def test_status_map_withdrawn_means_abolished():
    """ahbz 返回 status='W' 应映射为'作废'（非'现行'）"""
    assert ahbz._STATUS_MAP.get("W") == "作废", f"W 应为作废，实际: {ahbz._STATUS_MAP.get('W')}"


def test_status_map_no_d_key():
    """ahbz 没有 'D' 状态（网站模板仅 A/W 两种）"""
    assert "D" not in ahbz._STATUS_MAP


# ── Task 3: _get_type 测试 ──

def test_get_type_gb():
    assert ahbz.AhbzAdapter._get_type("GB/T 1.1-2020") == 1


def test_get_type_industry():
    assert ahbz.AhbzAdapter._get_type("SH/T 3098-2025") == 2
    assert ahbz.AhbzAdapter._get_type("NBSHT 137-2013") == 2


def test_get_type_db():
    assert ahbz.AhbzAdapter._get_type("DB22/T 2883-2018") == 3


def test_get_type_foreign():
    assert ahbz.AhbzAdapter._get_type("API 6D-2008") == 4
    assert ahbz.AhbzAdapter._get_type("ASME B16.5-2017") == 4


def test_get_type_group():
    assert ahbz.AhbzAdapter._get_type("TCCSAS 42-2023") == 5


def test_get_type_enterprise_returns_none():
    """企业标准 SG：ahbz 不支持，返回 None"""
    assert ahbz.AhbzAdapter._get_type("SG 1-2017") is None


def test_type_map_covers_all_valid():
    """_TYPE_MAP 覆盖 classify_std_code 所有有效返回值（enterprise 除外）"""
    valid = {"gb", "industry", "db", "iso_iec", "foreign", "group"}
    for v in valid:
        assert v in ahbz.AhbzAdapter._TYPE_MAP, f"{v} 应在 _TYPE_MAP 中"


# ── Task 6: 结构化匹配测试 ──

def test_match_structured_identical():
    """标准号完全相同应匹配"""
    rows = [{"code": "GB/T 1.1-2020", "csName": "标准化工作导则", "status": "A"}]
    result = ahbz.AhbzAdapter._match_structured("GB/T 1.1-2020", rows)
    assert result is not None
    assert result["code"] == "GB/T 1.1-2020"


def test_match_structured_prefix_suffix():
    """num_prefix（ASME B16.5-2017）应匹配"""
    rows = [{"code": "ASME B16.5-2017", "csName": "管法兰", "status": "A"}]
    result = ahbz.AhbzAdapter._match_structured("ASME B16.5-2017", rows)
    assert result is not None


def test_match_structured_api_num_suffix():
    """num_suffix（API 6D-2008）应匹配"""
    rows = [{"code": "API 6D-2008", "csName": "管线阀门", "status": "A"}]
    result = ahbz.AhbzAdapter._match_structured("API 6D-2008", rows)
    assert result is not None


def test_match_structured_no_match():
    """不同标准号不应匹配"""
    rows = [{"code": "GB/T 1.1-2020", "csName": "标准化工作导则", "status": "A"}]
    result = ahbz.AhbzAdapter._match_structured("GB/T 19001-2016", rows)
    assert result is None
