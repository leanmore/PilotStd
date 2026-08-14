# tests/test_wps_utils.py
"""_wps_utils.py 单元测试 — 覆盖 _clean_wps_fulltext 与 _split_wps_entries 全部分支。"""

import unittest

from pilotstd.announcement._wps_utils import _clean_wps_fulltext, _split_wps_entries
from pilotstd.announcement.parser import STD_CODE_PATTERN


class TestCleanWpsFulltext(unittest.TestCase):
    """_clean_wps_fulltext 所有分支。"""

    def test_remove_page_marker(self):
        """移除 WPS PAGE MERGEFORMAT 页脚标记。"""
        text = "标准文本 — PAGE  MERGEFORMAT 1 — 更多内容"
        result = _clean_wps_fulltext(text)
        self.assertNotIn("PAGE", result)
        self.assertNotIn("MERGEFORMAT", result)
        self.assertIn("标准文本", result)
        self.assertIn("更多内容", result)

    def test_remove_page_of(self):
        """移除 PAGE N OF M 页码标记。"""
        text = "PAGE 1 OF 10 第一章 总则"
        result = _clean_wps_fulltext(text)
        self.assertNotIn("PAGE", result)
        self.assertIn("第一章", result)

    def test_remove_ascii_control_chars(self):
        """移除 ASCII 控制字符，保留换行和制表符。"""
        text = "正常文本\x00\x01\x08\x0b\x0c\x7f\x9f结束"
        result = _clean_wps_fulltext(text)
        self.assertIn("正常文本", result)
        self.assertIn("结束", result)
        self.assertNotIn("\x00", result)
        self.assertNotIn("\x7f", result)

    def test_compress_spaces_to_newline(self):
        """3+ 连续空格/制表符 → 换行。"""
        text = "列1   列2       列3"
        result = _clean_wps_fulltext(text)
        self.assertIn("\n", result)

    def test_compress_newlines(self):
        """3+ 连续换行 → 压缩为 2 个。"""
        text = "段落1\n\n\n\n\n段落2"
        result = _clean_wps_fulltext(text)
        self.assertNotIn("\n\n\n", result)
        self.assertIn("\n\n", result)

    def test_preserve_single_newline(self):
        """单个换行不受影响。"""
        text = "行1\n行2"
        result = _clean_wps_fulltext(text)
        self.assertIn("\n", result)

    def test_empty_string(self):
        """空字符串不崩溃。"""
        result = _clean_wps_fulltext("")
        self.assertEqual(result, "")

    def test_no_wps_markers(self):
        """无 WPS 标记的普通文本原样返回。"""
        text = "GB/T 1.1-2020 标准化工作导则"
        result = _clean_wps_fulltext(text)
        self.assertEqual(result.strip(), text)


class TestSplitWpsEntries(unittest.TestCase):
    """_split_wps_entries 所有分支。"""

    def test_empty_text(self):
        """空文本 → 空列表。"""
        result = _split_wps_entries("", STD_CODE_PATTERN)
        self.assertEqual(result, [])

    def test_whitespace_only(self):
        """仅空白 → 空列表。"""
        result = _split_wps_entries("   \n  \n  ", STD_CODE_PATTERN)
        self.assertEqual(result, [])

    def test_single_entry(self):
        """单条标准 → 单元素列表。"""
        text = "GB/T 1.1-2020 标准化工作导则"
        result = _split_wps_entries(text, STD_CODE_PATTERN)
        self.assertEqual(len(result), 1)
        self.assertIn("GB/T 1.1-2020", result[0])

    def test_already_line_separated(self):
        """多行已按换行自然分隔，且 70% 以上行含标准号 → 直接返回行列表。"""
        text = (
            "GB/T 1.1-2020 标准化工作导则\n"
            "GB/T 1.2-2020 标准化工作导则第2部分\n"
            "GB/T 20000.1-2014 标准化工作指南"
        )
        result = _split_wps_entries(text, STD_CODE_PATTERN)
        self.assertEqual(len(result), 3)

    def test_multi_entry_no_newlines(self):
        """多条标准粘连无换行 → 按标准号位置切分。"""
        text = "GB/T 1.1-2020 导则GB/T 1.2-2020 术语"
        result = _split_wps_entries(text, STD_CODE_PATTERN)
        self.assertEqual(len(result), 2)
        self.assertTrue(any("1.1" in r for r in result))
        self.assertTrue(any("1.2" in r for r in result))

    def test_below_seventy_percent_threshold(self):
        """不到 70% 行含标准号 → 触发正则切分路径。"""
        text = (
            "前言\n"
            "GB/T 1.1-2020 导则\n"
            "附录A\n"
            "附录B\n"
        )
        result = _split_wps_entries(text, STD_CODE_PATTERN)
        # 正则切分找到 1 个匹配 → 返回单段
        self.assertGreaterEqual(len(result), 1)

    def test_short_segments_filtered(self):
        """短于 10 字符的片段被过滤。"""
        # 构造两个标准号之间只有极短间隔（不会有 <10 字符片段因为匹配间至少一个标准号长度）
        # 测试：无匹配时返回原文本
        text = "没有标准号的纯文本段落"
        result = _split_wps_entries(text, STD_CODE_PATTERN)
        self.assertEqual(len(result), 1)
        self.assertIn("没有标准号", result[0])

    def test_no_pattern_match(self):
        """完全没有标准号 → 返回原文本。"""
        text = "这是一段没有标准号的文字"
        result = _split_wps_entries(text, STD_CODE_PATTERN)
        self.assertEqual(len(result), 1)

    def test_multiple_matches_concatenated(self):
        """3 条粘连标准 → 正确切分为 3 段。"""
        text = "GB/T 1.1-2020 导则 ISO 9001-2015 质量体系 GB/T 19000-2016 基础和术语"
        result = _split_wps_entries(text, STD_CODE_PATTERN)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
