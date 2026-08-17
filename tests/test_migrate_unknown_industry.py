# tests/test_migrate_unknown_industry.py — 误归档迁移脚本核心逻辑测试

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.organizer.industry_lookup import get_folder_name
from scripts.migrate_unknown_industry import recover_logical_code


class TestRecoverLogicalCode(unittest.TestCase):
    def test_plain_letter_code(self):
        self.assertEqual(recover_logical_code(" GB 150-2011 压力容器.pdf", 150, 2011), "GB")
        self.assertEqual(recover_logical_code(" AQ 3026-2026 化工规范.pdf", 3026, 2026), "AQ")
        self.assertEqual(recover_logical_code(" HG 3001-2020 化工产品.pdf", 3001, 2020), "HG")

    def test_slash_code(self):
        self.assertEqual(recover_logical_code(" GB/T13793-2008 直缝电焊钢管.pdf", 13793, 2008), "GB/T")

    def test_db_code_with_duplicated_number(self):
        # DB 文件因 logical_code 含 number，误归档时 number 被重复拼接
        self.assertEqual(
            recover_logical_code(" DB 22/T28832883-2018 化工行业.pdf", 2883, 2018),
            "DB 22/T2883",
        )
        self.assertEqual(
            recover_logical_code(" DB 50/T19821982-2026 畜禽粪肥.pdf", 1982, 2026),
            "DB 50/T1982",
        )

    def test_short_number_code(self):
        self.assertEqual(recover_logical_code(" API 6-2008 管线阀门.pdf", 6, 2008), "API")
        self.assertEqual(recover_logical_code(" API 2000-2014 储罐.pdf", 2000, 2014), "API")

    def test_no_year_marker_returns_empty(self):
        self.assertEqual(recover_logical_code(" GB 150 压力容器.pdf", 150, 2011), "")


class TestRecoverThenFolder(unittest.TestCase):
    def test_db_code_maps_to_province(self):
        folder = get_folder_name(recover_logical_code(" DB 22/T28832883-2018 化工行业.pdf", 2883, 2018))
        self.assertIn("DB 地方标准", folder)
        self.assertIn("吉林", folder)

    def test_gb_code_maps_to_national(self):
        folder = get_folder_name(recover_logical_code(" GB 150-2011 压力容器.pdf", 150, 2011))
        self.assertIn("GB", folder)
        self.assertIn("国家标准", folder)


if __name__ == "__main__":
    unittest.main()
