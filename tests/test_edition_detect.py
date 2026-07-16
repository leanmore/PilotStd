# tests/test_edition_detect.py — 版次识别模块测试

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.scan.edition_detect import edition_skip_pattern, extract_edition


class TestExtractEdition(unittest.TestCase):
    def test_chinese_number_edition(self):
        self.assertEqual(extract_edition("标准 10版 中文版", "中文版"), "第10版")
        self.assertEqual(extract_edition("标准 第5版", "中文版"), "第5版")

    def test_chinese_edition_no_prefix(self):
        self.assertEqual(extract_edition("GB/T 1.1 3版", "中文版"), "第3版")

    def test_english_ordinal_to_chinese(self):
        self.assertEqual(extract_edition("ASME BPVC 10th 中文版", "中文版"), "第10版")
        self.assertEqual(extract_edition("Standard 5th", "中文版"), "第5版")

    def test_english_ordinal_kept_for_english(self):
        self.assertEqual(extract_edition("ASME BPVC 10th", "英文版"), "10th")
        self.assertEqual(extract_edition("Standard 5th", "英文版"), "5th")

    def test_english_word_edition(self):
        self.assertEqual(extract_edition("Standard Tenth Edition", "英文版"), "Tenth Edition")
        self.assertEqual(extract_edition("Standard Fifth Edition", "英文版"), "Fifth Edition")

    def test_english_word_to_chinese(self):
        self.assertEqual(extract_edition("Standard Fifth Edition", "中文版"), "第5版")
        self.assertEqual(extract_edition("Standard Third Edition 中文", "中文版"), "第3版")

    def test_no_edition_returns_empty(self):
        self.assertEqual(extract_edition("GB/T 1.1-2020", "中文版"), "")
        self.assertEqual(extract_edition("ISO 9001:2015", "英文版"), "")

    def test_unknown_ordinal(self):
        result = extract_edition("Standard 99th", "英文版")
        self.assertEqual(result, "99th")


class TestEditionSkipPattern(unittest.TestCase):
    def test_returns_non_empty(self):
        pattern = edition_skip_pattern()
        self.assertIsInstance(pattern, str)
        self.assertGreater(len(pattern), 0)

    def test_matches_chinese_edition(self):
        import re

        pattern = edition_skip_pattern()
        self.assertTrue(re.search(pattern, "10版"))
        self.assertTrue(re.search(pattern, " 第5版 "))

    def test_matches_english_edition(self):
        import re

        pattern = edition_skip_pattern()
        self.assertTrue(re.search(pattern, "Tenth Edition"))


if __name__ == "__main__":
    unittest.main()
