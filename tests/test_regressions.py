# tests/test_regressions.py
# 回归测试：覆盖 2026-06-08 修复的底层 bug
# - _search/_parse_result 自比较 bug（njbz365/hbba/dbba/iso_gov）
# - 下载 source_site 传递 + can_handle 过宽
# - _find_adapter 站点名映射

import sys
import os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from pilotstd.query.models import QueryResult
from pilotstd.query.adapters.njbz365 import Njbz365Adapter, _parse_result_number as njbz_parse
from pilotstd.query.adapters.hbba import HbbaAdapter
from pilotstd.query.adapters.dbba import DbbaAdapter
from pilotstd.query.adapters.iso_gov import IsoGovAdapter
from pilotstd.query.search_strategy import match_result, _parse_result_number
from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
from pilotstd.download.engine import DownloadEngine
from pilotstd.download.models import DownloadTask
from pilotstd.download.session import SessionManager


# ════════════════════════════════════════════════════════════════
# 1. match_result 参数语义验证
# ════════════════════════════════════════════════════════════════

class TestMatchResultSemantics(unittest.TestCase):
    """验证 match_result 不会误将 API 返回值自比较。
    前三个参数 (local_code, local_number, local_year) 是搜索目标，
    后两个是 API 返回结果。两者不同时应返回非 exact 状态。"""

    def test_self_comparison_always_exact(self):
        """自比较永远是 exact——这正是我们要防止的。"""
        _, status = match_result("API", 610, 2004, "API Std 610-2004", "API 610-2004")
        self.assertEqual(status, "exact")

    def test_different_code_returns_mismatch(self):
        """搜索 API 610-2004，API 返回 GB/T 19001-2016 → 应返回 mismatch。"""
        _, status = match_result("API", 610, 2004, "质量管理体系", "GB/T 19001-2016")
        self.assertEqual(status, "mismatch")

    def test_same_number_different_code_older(self):
        """同序号不同代号：搜索 JB 4732-1995，API 返回 GB 150-2011 → 代号不匹配 → mismatch"""
        _, status = match_result("JB", 4732, 1995, "钢制压力容器", "GB 150-2011")
        self.assertEqual(status, "mismatch")

    def test_code_variant_still_matches(self):
        """GB ↔ GB/T 变体：搜索 GB/T 19001-2016，返回 GB 19001-2020 → newer"""
        _, status = match_result("GB/T", 19001, 2016, "质量管理体系", "GB 19001-2020")
        self.assertEqual(status, "newer")

    def test_newer_detected(self):
        """搜索 GB/T 19001-2016，返回 GB/T 19001-2020 → newer"""
        _, status = match_result("GB/T", 19001, 2016, "质量管理体系", "GB/T 19001-2020")
        self.assertEqual(status, "newer")

    def test_match_result_uses_local_not_result_params(self):
        """核心验证：local_code/number/year 来自搜索目标而非 API 结果。
        搜索「API 610 2004」，API 返回 ISO 9001-2015 →
        因为代号(API vs ISO)不同 → mismatch"""
        _, status = match_result("API", 610, 2004, "Quality systems", "ISO 9001-2015")
        self.assertEqual(status, "mismatch")


# ════════════════════════════════════════════════════════════════
# 2. njbz365 _search 自比较修复验证
# ════════════════════════════════════════════════════════════════

class TestNjbz365SearchFix(unittest.TestCase):
    """验证 njbz365._search 用搜索目标参数比对，而非自比较。"""

    def setUp(self):
        self.adapter = Njbz365Adapter()

    def _fake_do_request(self, data):
        """模拟 njbz365 API 返回 GB/T 19001-2016（与我们搜索的目标不同）。"""
        return {
            "code": "0",
            "data": {
                "datalist": [{
                    "bzbh": "GB/T 19001-2016",
                    "bzmc": "质量管理体系 要求",
                    "bzzt": "现行",
                    "bzid": "12345",
                    "cybz": "",
                    "fbrq": "2016-12-30",
                    "ssrq": "2017-07-01",
                }]
            }
        }

    def test_search_with_target_params_detects_exact(self):
        """传入正确的目标参数 → API 返回了匹配的结果 → exact"""
        adapter = self.adapter
        adapter._do_request = MagicMock(return_value={
            "code": "0",
            "data": {
                "datalist": [{
                    "bzbh": "API 610-2004",
                    "bzmc": "Centrifugal Pumps",
                    "bzzt": "现行",
                    "bzid": "67890",
                    "cybz": "",
                    "fbrq": "2004-01-01",
                    "ssrq": "2004-06-01",
                }]
            }
        })
        result = adapter._search("API 610 2004", target_code="API",
                                 target_number=610, target_year=2004)
        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "exact")

    def test_search_with_target_params_detects_mismatch(self):
        """传入 API 搜索目标，但 API 返回了 GB/T → mismatch"""
        adapter = self.adapter
        adapter._do_request = MagicMock(return_value=self._fake_do_request(None))
        result = adapter._search("API 610 2004", target_code="API",
                                 target_number=610, target_year=2004)
        self.assertIsNotNone(result)
        self.assertNotEqual(result.match_status, "exact",
                           "搜索 API 但 API 返回 GB/T → 不应该是 exact")

    def test_search_without_target_params_uses_empty(self):
        """不传目标参数时 match_result 收到空字符串 → 应返回非 exact"""
        adapter = self.adapter
        adapter._do_request = MagicMock(return_value=self._fake_do_request(None))
        result = adapter._search("API 610 2004")
        self.assertIsNotNone(result)
        # 空字符串代号 vs GB/T → 不应该是 exact
        self.assertNotEqual(result.match_status, "exact")

    def test_query_single_parses_target_from_number(self):
        """query_single 从 standard_number 解析目标参数传给 _search。"""
        adapter = self.adapter
        adapter._do_request = MagicMock(return_value=self._fake_do_request(None))
        result = adapter.query_single("API 610-2004")
        self.assertIsNotNone(result)
        # API 目标 vs GB/T 返回 → 不应该是 exact
        self.assertNotEqual(result.match_status, "exact")


# ════════════════════════════════════════════════════════════════
# 3. hbba/dbba/iso_gov _parse_result 自比较修复验证
# ════════════════════════════════════════════════════════════════

class TestHbbaParseResultFix(unittest.TestCase):
    """验证 hbba._parse_result 用 search_term 解析目标参数比对。"""

    def setUp(self):
        self.adapter = HbbaAdapter()

    def _make_rec(self, code="SH/T 1610-2011", ch_name="苯乙烯-丁二烯橡胶"):
        return {"code": code, "chName": ch_name, "status": "现行",
                "pk": "12345", "issueDate": 1293811200000,
                "actDate": 1293811200000, "chargeDept": "全国橡胶委"}

    def test_parse_result_with_matching_search_term(self):
        """search_term 与 API 结果匹配 → exact"""
        rec = self._make_rec("SH/T 1610-2011")
        result = self.adapter._parse_result(rec, "SH/T 1610-2011")
        self.assertEqual(result.match_status, "exact")

    def test_parse_result_with_mismatched_search_term(self):
        """search_term 与 API 结果不匹配 → 不应是 exact"""
        rec = self._make_rec("SH/T 1610-2011")
        result = self.adapter._parse_result(rec, "SH/T 1752-2006")
        self.assertNotEqual(result.match_status, "exact",
                           "搜索 SH/T 1752 但 API 返回 SH/T 1610 → 不应该是 exact")

    def test_parse_result_without_search_term(self):
        """无 search_term 时目标参数为空 → 不应是 exact（除非同为空的巧合）"""
        rec = self._make_rec()
        result = self.adapter._parse_result(rec, "")
        # 空目标 vs SH/T 1610 → 不应该是 exact
        self.assertNotEqual(result.match_status, "exact")


class TestDbbaParseResultFix(unittest.TestCase):
    """验证 dbba._parse_result 用 search_term 解析目标参数比对。"""

    def setUp(self):
        self.adapter = DbbaAdapter()

    def _make_rec(self, code="DB35 1234-2020", ch_name="福建省地方标准"):
        return {"code": code, "chName": ch_name, "status": "现行",
                "pk": "12345", "issueDate": 1577836800000,
                "actDate": 1577836800000, "chargeDept": ""}

    def test_parse_result_exact_when_matching(self):
        rec = self._make_rec()
        result = self.adapter._parse_result(rec, "DB35 1234-2020")
        self.assertEqual(result.match_status, "exact")

    def test_parse_result_not_exact_when_mismatched(self):
        rec = self._make_rec("DB35 1234-2020")
        result = self.adapter._parse_result(rec, "DB35 5678-2020")
        self.assertNotEqual(result.match_status, "exact")


class TestIsoGovParseResultFix(unittest.TestCase):
    """验证 iso_gov._parse_result 用 search_term 解析目标参数比对。"""

    def setUp(self):
        self.adapter = IsoGovAdapter()

    def _make_row(self, std_no="ISO 9001:2015", en_name="Quality management systems"):
        return {"STANDARD_NO": std_no, "ENGLISH_NAME": en_name,
                "STATE": "现行", "CIRCULATION_DATE": "2015-09-15",
                "STANDARD_STATUS": "ACTIVE", "YEAR_DATE": 2015,
                "PUBLISH_UNIT": "ISO", "id": "iso_9001"}

    def test_parse_result_exact_when_matching(self):
        row = self._make_row()
        result = self.adapter._parse_result(row, "ISO 9001:2015")
        self.assertEqual(result.match_status, "exact")

    def test_parse_result_not_exact_when_mismatched_year(self):
        row = self._make_row("ISO 9001:2015")
        result = self.adapter._parse_result(row, "ISO 9001:2008")
        self.assertNotEqual(result.match_status, "exact")

    def test_parse_result_not_exact_when_mismatched_number(self):
        row = self._make_row("ISO 9001:2015")
        result = self.adapter._parse_result(row, "ISO 14001:2015")
        self.assertNotEqual(result.match_status, "exact")


# ════════════════════════════════════════════════════════════════
# 4. 下载 source_site 传递 + can_handle 修复验证
# ════════════════════════════════════════════════════════════════

class TestDownloadSourceSitePropagation(unittest.TestCase):
    """验证 DownloadTask.source_site 正确传递 + can_handle 不会误匹配。"""

    def test_can_handle_rejects_empty_source_site(self):
        """修复后 can_handle 不再对空 source_site 返回 True。"""
        adapter = OpenstdDownloadAdapter()
        task = DownloadTask(standard_number="GB/T 1-2020", source_site="")
        self.assertFalse(adapter.can_handle(task),
                        "空 source_site 不应被 openstd 适配器接受")

    def test_can_handle_accepts_openstd_download(self):
        """明确标记为 openstd_download 的任务应被接受。"""
        adapter = OpenstdDownloadAdapter()
        task = DownloadTask(standard_number="GB/T 1-2020",
                            source_site="openstd_download")
        self.assertTrue(adapter.can_handle(task))

    def test_can_handle_rejects_foreign_site(self):
        """njbz365 / hbba 等非 openstd 站点不应被接受。"""
        adapter = OpenstdDownloadAdapter()
        for site in ("njbz365", "hbba", "dbba", "iso_gov", "csres"):
            task = DownloadTask(standard_number="API 610-2004", source_site=site)
            self.assertFalse(adapter.can_handle(task),
                            f"site={site} 不应被 openstd 适配器接受")

    def test_find_adapter_maps_std_gov_to_openstd(self):
        """_QUERY_TO_DOWNLOAD_SITE 映射：std_gov → openstd_download"""
        adapter = OpenstdDownloadAdapter()
        engine = DownloadEngine(adapters=[adapter],
                                session_manager=MagicMock())
        task = DownloadTask(standard_number="GB/T 19001-2016",
                            source_site="std_gov")
        found = engine._find_adapter(task)
        self.assertIsNotNone(found, "std_gov 应通过映射找到 openstd_download 适配器")
        self.assertEqual(found.site_name, "openstd_download")

    def test_find_adapter_returns_none_for_foreign_standard(self):
        """国外标准（njbz365 等查询结果）→ 无下载适配器 → 返回 None"""
        adapter = OpenstdDownloadAdapter()
        engine = DownloadEngine(adapters=[adapter],
                                session_manager=MagicMock())
        task = DownloadTask(standard_number="API 610-2004",
                            source_site="njbz365")
        found = engine._find_adapter(task)
        self.assertIsNone(found,
                         "njbz365 来源的国外标准不应有下载适配器，应返回清晰错误而非缺hcno")

    def test_download_task_accepts_source_site_param(self):
        """DownloadTask 可以接受 source_site 参数。"""
        task = DownloadTask(standard_number="GB/T 1-2020",
                            source_site="std_gov")
        self.assertEqual(task.source_site, "std_gov")


# ════════════════════════════════════════════════════════════════
# 5. ParsedStdInfo found_source_site 字段
# ════════════════════════════════════════════════════════════════

class TestFoundSourceSiteField(unittest.TestCase):
    """验证 ParsedStdInfo 新增的 found_source_site 字段。"""

    def test_field_exists_with_default(self):
        from pilotstd.models import ParsedStdInfo
        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB/T",
                          number=1, year=2020)
        self.assertEqual(p.found_source_site, "")

    def test_field_can_be_set(self):
        from pilotstd.models import ParsedStdInfo
        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB/T",
                          number=1, year=2020)
        p.found_source_site = "std_gov"
        self.assertEqual(p.found_source_site, "std_gov")


if __name__ == "__main__":
    unittest.main()
