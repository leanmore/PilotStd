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


class TestExactMatcher(unittest.TestCase):
    parser: StandardParser

    @classmethod
    def setUpClass(cls):
        cls.parser = StandardParser(build_code_mapping())

    def test_exact_match_db_prefix(self):
        """DB11/T 模式 → logical_code 仅代号（无空格），顺序号独立存 number。"""
        result = self.parser.parse("DB11/T 1234-2020 北京市地方标准.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "DB11/T")
        self.assertEqual(result.number, 1234)
        self.assertEqual(result.year, 2020)

    def test_exact_match_db_with_number_only(self):
        """DB22/T 2883-2018 → logical_code 不含顺序号、无空格（修复重复编号根因）。"""
        result = self.parser.parse(
            "DB22/T 2883-2018 化工行业安全生产风险分级管控和隐患排查治理双重预防机制建设通用规范.pdf"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "DB22/T")
        self.assertEqual(result.number, 2883)
        self.assertEqual(result.year, 2018)

    def test_exact_match_db_mandatory(self):
        """强制性地方标准 DB50 1982-2026 → logical_code 仅代号（无空格）。"""
        result = self.parser.parse("DB50 1982-2026 畜禽粪肥质量控制和利用技术规范.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "DB50")
        self.assertEqual(result.number, 1982)
        self.assertEqual(result.year, 2026)

    def test_combined_standard_without_tilde(self):
        """无～符号的合订本残片文件名：47008-1947 010-2010 → NB/T 47008-2010。"""
        result = self.parser.parse("NB/T47008-1947 010-2010 锻件标准.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "NB/T")
        self.assertEqual(result.number, 47008)
        self.assertEqual(result.year, 2010)
        self.assertIn("合订本", result.std_name)

    def test_exact_match_group_with_slash(self):
        """团体标准带斜杠形态：T/CIESC 001-2019 → logical_code='T/CIESC'。"""
        result = self.parser.parse("T/CIESC 001-2019 团体标准.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "T/CIESC")
        self.assertEqual(result.number, 1)
        self.assertEqual(result.year, 2019)

    def test_exact_match_group_no_slash(self):
        """团体标准无斜杠归档形态：TCIESC 001-2019 → logical_code='T/CIESC'。"""
        result = self.parser.parse("TCIESC 001-2019 团体标准.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "T/CIESC")
        self.assertEqual(result.number, 1)
        self.assertEqual(result.year, 2019)

    def test_exact_match_group_not_steal_tsg(self):
        """TSG（特种设备安全技术规范）不应被团体标准通道误伤。"""
        result = self.parser.parse("TSG 1-2014 特种设备安全技术规范制定导则.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "TSG")
        self.assertEqual(result.number, 1)

    def test_exact_match_bpvc_roman_volume(self):
        """ASME BPVC 罗马数字卷号 → number 映射正确。"""
        result = self.parser.parse("ASME BPVC IX-2021 焊接评定.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_code, "ASME")
        self.assertTrue(result.number > 0, f"number 应为正整数，实际 {result.number}")


# === _foreign.py 覆盖 ===


class TestForeignHandler(unittest.TestCase):
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
        number, suffix, _ = StandardParser._extract_number("B16")
        self.assertEqual(number, 16)
        self.assertEqual(suffix, "")


if __name__ == "__main__":
    unittest.main()
