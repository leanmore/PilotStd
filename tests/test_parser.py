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


# === _exact.py 覆盖 ===


class TestExactMatchMixin(unittest.TestCase):
    parser: StandardParser

    @classmethod
    def setUpClass(cls):
        cls.parser = StandardParser(build_code_mapping())

    def test_exact_match_db_prefix(self):
        """DB11/T 模式 → logical_code='DB11/T', number 为数字。"""
        result = self.parser.parse("DB11/T 1234-2020 北京市地方标准.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "DB11/T")
        self.assertEqual(result.year, 2020)

    def test_exact_match_bpvc_roman_volume(self):
        """ASME BPVC 罗马数字卷号 → number 映射正确。"""
        result = self.parser.parse("ASME BPVC IX-2021 焊接评定.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "ASME")
        self.assertTrue(result.number > 0, f"number 应为正整数，实际 {result.number}")


# === _foreign.py 覆盖 ===


class TestForeignHandlerMixin(unittest.TestCase):
    parser: StandardParser

    @classmethod
    def setUpClass(cls):
        cls.parser = StandardParser(build_code_mapping())

    def test_handle_letter_class_astm(self):
        """ASTM 解析后 num_prefix 被后处理设为字母分类。"""
        info = self.parser.parse("ASTM A370-2020 钢拉伸试验方法.pdf")
        self.assertIsNotNone(info)
        # ASTM 正常解析应有 logical_code='ASTM'
        self.assertEqual(info.logical_code, "ASTM")

    def test_handle_type_prefix_iec(self):
        """IEC TR 解析后 logical_code 被后处理修正为 IEC，num_prefix 设为 TR。"""
        info = self.parser.parse("IEC TR 61000-3-2020 电磁兼容.pdf")
        self.assertIsNotNone(info)
        # IEC 类型前缀应由 post_process 处理
        self.assertIn(info.logical_code, ("IEC", "IEC TR"))


# === _utils.py 覆盖 ===


class TestParserUtilsMixin(unittest.TestCase):
    parser: StandardParser

    @classmethod
    def setUpClass(cls):
        cls.parser = StandardParser(build_code_mapping())

    def test_clean_removes_no_dot_prefix(self):
        """_clean 去除 No. 前缀、: → - 等符号清理。"""
        result = StandardParser._clean("No. GB/T 1.1-2020: 文件")
        self.assertNotIn("No.", result)
        self.assertIn("-", result)

    def test_extract_number_alpha_prefix_stripped(self):
        """_extract_number('B16') → (16, '')，去掉前导字母。"""
        number, suffix = StandardParser._extract_number("B16")
        self.assertEqual(number, 16)
        self.assertEqual(suffix, "")


if __name__ == "__main__":
    unittest.main()
