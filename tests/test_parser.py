"""解析器自查校验测试"""

import unittest

from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser


class TestParserValidation(unittest.TestCase):
    parser: StandardParser

    @classmethod
    def setUpClass(cls):
        cls.parser = StandardParser(build_code_mapping())

    def test_reject_year_zero(self):
        """SH/T 代号无年份时解析器应拒绝"""
        # 这些是表单模板文件，有代号和数字但无年份
        self.assertIsNone(self.parser.parse("SH/T 3503-J801 起重机安装检查记录.doc"))
        self.assertIsNone(self.parser.parse("SH/T 3543-G101A 封面.doc"))

    def test_reject_invalid_year(self):
        """年份不在合理范围应拒绝"""
        self.assertIsNone(self.parser.parse("GB/T 1.1-0.pdf"))
        self.assertIsNone(self.parser.parse("GB/T 1.1-1800.pdf"))
        self.assertIsNone(self.parser.parse("GB/T 1.1-2100.pdf"))

    def test_accept_two_digit_year(self):
        """两位年份应接受并规范化"""
        result = self.parser.parse("GB/T 1-98.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 1998)  # _normalize_year 会将 98 → 1998

    def test_normal_files_still_parse(self):
        """正常文件应仍然通过"""
        result = self.parser.parse("SH/T 3503-2017 交工技术文件规定.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2017)
        self.assertEqual(result.number, 3503)

    def test_reject_junk_filename(self):
        """无标准代号的垃圾文件名应拒绝"""
        self.assertIsNone(self.parser.parse("J801 起重机.doc"))
        self.assertIsNone(self.parser.parse("G101A 封面.doc"))

    def test_reject_year_9999(self):
        """年份为全9等异常值应拒绝"""
        self.assertIsNone(self.parser.parse("GB/T 1.1-9999.pdf"))


if __name__ == "__main__":
    unittest.main()
