# tests/test_industry_lookup.py — 行业代号查找模块补充测试

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.organizer.industry_lookup import (
    build_code_mapping,
    get_base_code,
    get_db_region,
    get_folder_name,
    get_industry_name,
    is_db_code,
)


class TestIsDbCode(unittest.TestCase):
    def test_db_with_province_code(self):
        self.assertTrue(is_db_code("DB11"))
        self.assertTrue(is_db_code("DB35"))
        self.assertTrue(is_db_code("DB65"))

    def test_db_with_city_code(self):
        self.assertTrue(is_db_code("DB3501"))
        self.assertTrue(is_db_code("DB4403"))

    def test_db_with_t_suffix(self):
        self.assertTrue(is_db_code("DB11/T"))
        self.assertTrue(is_db_code("DB3501/T"))

    def test_non_db_codes(self):
        self.assertFalse(is_db_code("GB"))
        self.assertFalse(is_db_code("GBT"))
        self.assertFalse(is_db_code("SH/T"))
        self.assertFalse(is_db_code("ISO"))


class TestGetDbRegion(unittest.TestCase):
    def test_known_provinces(self):
        self.assertEqual(get_db_region("DB11"), "北京")
        self.assertEqual(get_db_region("DB31"), "上海")
        self.assertEqual(get_db_region("DB44"), "广东")

    def test_with_t_suffix(self):
        self.assertEqual(get_db_region("DB11/T"), "北京")

    def test_unknown_region(self):
        self.assertEqual(get_db_region("DB99"), "地方标准")

    def test_non_db_code(self):
        self.assertEqual(get_db_region("GB"), "地方标准")


class TestGetBaseCode(unittest.TestCase):
    def test_standard_codes(self):
        self.assertEqual(get_base_code("GB/T"), "GB")
        self.assertEqual(get_base_code("SH/T"), "SH")
        self.assertEqual(get_base_code("GB"), "GB")

    def test_historical_variants(self):
        self.assertEqual(get_base_code("SHB"), "SH")
        self.assertEqual(get_base_code("SHJ"), "SH")
        self.assertEqual(get_base_code("SHS"), "SH")

    def test_multi_word_foreign_prefix(self):
        self.assertEqual(get_base_code("BS EN"), "BS")
        self.assertEqual(get_base_code("DIN EN ISO"), "DIN")

    def test_composite_prefix(self):
        self.assertEqual(get_base_code("NBSHT"), "NB")
        self.assertEqual(get_base_code("JBZQ"), "JB")


class TestGetIndustryName(unittest.TestCase):
    def test_national_code(self):
        self.assertEqual(get_industry_name("GB"), "国家标准")

    def test_foreign_code(self):
        self.assertEqual(get_industry_name("ISO"), "国际标准化组织")
        self.assertEqual(get_industry_name("DIN"), "德国标准化学会")

    def test_industry_code(self):
        self.assertEqual(get_industry_name("HG"), "化工")
        self.assertEqual(get_industry_name("JB"), "机械")

    def test_unknown_code(self):
        result = get_industry_name("XYZ123")
        self.assertIn("未知行业", result)


class TestBuildCodeMapping(unittest.TestCase):
    def test_includes_gb_variants(self):
        mapping = build_code_mapping()
        self.assertIn("GB", mapping)
        self.assertIn("GBT", mapping)
        self.assertEqual(mapping["GBT"], "GB/T")
        self.assertIn("GBZ", mapping)
        self.assertEqual(mapping["GBZ"], "GB/Z")

    def test_includes_industry_t_variants(self):
        mapping = build_code_mapping()
        self.assertIn("HGT", mapping)
        self.assertEqual(mapping["HGT"], "HG/T")
        self.assertIn("JBT", mapping)
        self.assertEqual(mapping["JBT"], "JB/T")

    def test_includes_db_province_codes(self):
        mapping = build_code_mapping()
        self.assertIn("DB11", mapping)
        self.assertEqual(mapping["DB11"], "DB11")
        self.assertIn("DB11T", mapping)
        self.assertEqual(mapping["DB11T"], "DB11/T")

    def test_foreign_codes_no_t_variant(self):
        mapping = build_code_mapping()
        self.assertIn("ISO", mapping)
        self.assertEqual(mapping["ISO"], "ISO")
        self.assertNotIn("ISOT", mapping)


class TestGetFolderName(unittest.TestCase):
    def test_gb_folder(self):
        name = get_folder_name("GB/T")
        self.assertIn("GB", name)
        self.assertIn("国家标准", name)

    def test_db_folder(self):
        name = get_folder_name("DB11/T")
        self.assertIn("DB 地方标准", name)
        self.assertIn("北京", name)

    def test_foreign_folder(self):
        name = get_folder_name("ISO")
        self.assertIn("ISO", name)
        self.assertIn("国际标准化组织", name)


if __name__ == "__main__":
    unittest.main()
