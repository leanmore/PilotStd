"""pilotstd/scan/filename_normalizer.py 补测 — 6 个正则模式的匹配/拒止/边界行为。"""
import re
import pytest
from pilotstd.scan.filename_normalizer import (
    _ZH_MARK,
    _EN_MARK,
    _EN_CN_CODE,
    _EDITION_ALL,
    _EDITION_HYBRID,
    _EXTRA_DESC,
)


class TestZhMark:
    """中文语种标记（_ZH_MARK）——正常×2 + 边界×1 + 异常×1 + 状态转换×1。"""

    def test_match_parentheses_chinese(self):
        """（中文版）/（中文）/ (中文版) 应被匹配。"""
        assert _ZH_MARK.search("GB/T 12345（中文版）")
        assert _ZH_MARK.search("GB/T 12345（中文）")
        assert _ZH_MARK.search("GB/T 12345(中文版)")

    def test_match_chinese_translation_and_cn_suffix(self):
        """--中文翻译 / _CN 后缀应被匹配。"""
        assert _ZH_MARK.search("标准名--中文翻译")
        assert _ZH_MARK.search("标准名_CN")
        assert _ZH_MARK.search("标准名-CN")

    def test_boundary_cn_not_in_standard_code(self):
        """BS EN 中的 EN 不应被 _ZH_MARK 匹配（保护标准代号段）。"""
        assert not _ZH_MARK.search("BS EN 12345")

    def test_exception_empty_input(self):
        """空字符串不引发异常，search 返回 None。"""
        assert _ZH_MARK.search("") is None

    def test_state_cn_after_chinese_char_vs_english(self):
        """中文字符后的 CN 被匹配，但英文字符后的 CN 不被匹配。"""
        assert _ZH_MARK.search("标准CN")  # 中文字符后
        # "StandardCN" 中的 CN 前是英文，不应匹配中文标记
        assert not _ZH_MARK.search("StandardCN")


class TestEnMark:
    """英文语种标记（_EN_MARK）——正常×2 + 边界×1 + 异常×1 + 状态转换×1。"""

    def test_match_english_markers(self):
        """（英文）/ English version / 英文版 应被匹配。"""
        assert _EN_MARK.search("标准名（英文）")
        assert _EN_MARK.search("标准名 English version")
        assert _EN_MARK.search("标准名 英文版")

    def test_match_en_after_chinese_char(self):
        """中文字符后的 en/EN 应被匹配。"""
        assert _EN_MARK.search("标准en")
        assert _EN_MARK.search("标准EN")

    def test_boundary_en_not_in_standard_code(self):
        """BS EN 中的 EN 不应被 _EN_MARK 匹配。"""
        assert not _EN_MARK.search("BS EN 12345")

    def test_exception_case_insensitive(self):
        """IGNORECASE 生效：english / ENGLISH 均匹配。"""
        assert _EN_MARK.search("标准名 English version")
        assert _EN_MARK.search("标准名 ENGLISH VERSION")

    def test_state_english_in_parentheses_vs_bare(self):
        """括号内的英文标记和裸标记应都能匹配。"""
        assert _EN_MARK.search("标准名(English)")
        assert _EN_MARK.search("标准名 English version")


class TestEnCnCode:
    """EN/CN 语言代码（_EN_CN_CODE）——保护标准代号段。"""

    def test_match_cn_after_digit(self):
        """数字后的 CN 应被匹配。"""
        assert _EN_CN_CODE.search("2000CN")

    def test_match_en_after_chinese_or_digit(self):
        """中文/数字后的 EN 应被匹配。"""
        assert _EN_CN_CODE.search("标准EN")
        assert _EN_CN_CODE.search("2000EN")

    def test_boundary_en_not_in_bs_en_prefix(self):
        """BS EN 中的 EN 不应被匹配（标准代号段保护）。"""
        assert not _EN_CN_CODE.search("BS EN 12345")

    def test_exception_standalone_en(self):
        """不在特定上下文中的 EN 不被匹配。"""
        assert not _EN_CN_CODE.search("EN 12345")

    def test_state_digit_followed_by_cn_then_separator(self):
        """_2000CN 模式：下划线+4位数字+CN 应被匹配。"""
        assert _EN_CN_CODE.search("_2000CN.pdf")


class TestEditionAll:
    """版次标记（_EDITION_ALL）——中文版次+英文序数版次。"""

    def test_match_chinese_edition(self):
        """第10版 / 10版 应被匹配。"""
        assert _EDITION_ALL.search("第10版")
        assert _EDITION_ALL.search("10版")
        assert _EDITION_ALL.search("第 1 版")

    def test_match_english_ordinal_edition(self):
        """10th / 5th / First Edition 应被匹配。"""
        assert _EDITION_ALL.search("10th")
        assert _EDITION_ALL.search("5th")
        assert _EDITION_ALL.search("First Edition")

    def test_boundary_not_match_random_number(self):
        """纯数字 12345 不应被匹配为版次。"""
        assert not _EDITION_ALL.search("12345")

    def test_exception_empty_input(self):
        """空输入不引发异常。"""
        assert _EDITION_ALL.search("") is None

    def test_state_hybrid_edition_language_in_parens(self):
        """(5th 中文版) 混合括号标记应被匹配。"""
        assert _EDITION_ALL.search("标准名(5th 中文版)")


class TestEditionHybrid:
    """版次嵌入型（_EDITION_HYBRID）——_5th / -5th-中文版 等嵌入模式。"""

    def test_match_underscore_ordinal(self):
        """_5th 嵌入版次应被匹配。"""
        assert _EDITION_HYBRID.search("标准_5th_标题")

    def test_match_dash_ordinal_with_language(self):
        """-5th-中文版 嵌入版次+语种应被匹配。"""
        assert _EDITION_HYBRID.search("标准-5th-中文版标题")

    def test_boundary_not_match_without_text_after(self):
        """版次标记后无文本字符不应匹配（需前瞻断言）。"""
        assert not _EDITION_HYBRID.search("标准_5th")

    def test_exception_single_digit_not_ordinal(self):
        """_5 不是合法版次标记（非序数）。"""
        assert not _EDITION_HYBRID.search("标准_5_标题")

    def test_state_ordinal_with_en_suffix(self):
        """_3rd-EN 嵌入版次+语种代码应被匹配。"""
        assert _EDITION_HYBRID.search("标准_3rd-EN标题")


class TestExtraDesc:
    """附加描述（_EXTRA_DESC）——+中英对照 / +N万字注解 / +N张附图。"""

    def test_match_bilingual_description(self):
        """+中英对照 应被匹配。"""
        assert _EXTRA_DESC.search("标准名 +中英对照")

    def test_match_word_count_and_illustration(self):
        """+3万字注解 / +160张附图 应被匹配。"""
        assert _EXTRA_DESC.search("标准名 +3万字注解")
        assert _EXTRA_DESC.search("标准名 +160张附图")

    def test_boundary_not_match_plain_plus_sign(self):
        """单独的 + 符号不应被匹配。"""
        assert not _EXTRA_DESC.search("标准名+")

    def test_exception_multiple_extensions(self):
        """+中英对照+3万字注解+160张附图 连续扩展应被完整匹配。"""
        m = _EXTRA_DESC.search("标准名+中英对照+3万字注解+160张附图")
        assert m
        assert "+中英对照" in m.group()

    def test_state_nested_descriptions_in_filename(self):
        """文件全名中的附加描述应被正确剥离定位。"""
        result = _EXTRA_DESC.search("GB/T 12345 标准标题+中英对照+5万字注解.pdf")
        assert result
        assert "+中英对照" in result.group()
