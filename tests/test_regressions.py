# tests/test_regressions.py
# 回归测试：覆盖 2026-06-08 修复的底层 bug
# - _search/_parse_result 自比较 bug（njbz365/hbba/dbba/iso_gov）
# - 下载 source_site 传递 + can_handle 过宽
# - _find_adapter 站点名映射

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest
from unittest.mock import MagicMock

from pilotstd.core.status import Status
from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
from pilotstd.download.engine import DownloadEngine
from pilotstd.download.models import DownloadStatus, DownloadTask
from pilotstd.query.adapters.dbba import DbbaAdapter
from pilotstd.query.adapters.hbba import HbbaAdapter
from pilotstd.query.adapters.iso_gov import IsoGovAdapter
from pilotstd.query.adapters.njbz365 import Njbz365Adapter
from pilotstd.query.search_strategy import match_result

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
                "datalist": [
                    {
                        "bzbh": "GB/T 19001-2016",
                        "bzmc": "质量管理体系 要求",
                        "bzzt": Status.ACTIVE.value,
                        "bzid": "12345",
                        "cybz": "",
                        "fbrq": "2016-12-30",
                        "ssrq": "2017-07-01",
                    }
                ]
            },
        }

    def test_search_with_target_params_detects_exact(self):
        """传入正确的目标参数 → API 返回了匹配的结果 → exact"""
        adapter = self.adapter
        adapter._do_request = MagicMock(
            return_value={
                "code": "0",
                "data": {
                    "datalist": [
                        {
                            "bzbh": "API 610-2004",
                            "bzmc": "Centrifugal Pumps",
                            "bzzt": Status.ACTIVE.value,
                            "bzid": "67890",
                            "cybz": "",
                            "fbrq": "2004-01-01",
                            "ssrq": "2004-06-01",
                        }
                    ]
                },
            }
        )
        result = adapter._search("API 610 2004", target_code="API", target_number=610, target_year=2004)
        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "exact")

    def test_search_with_target_params_detects_mismatch(self):
        """传入 API 搜索目标，但 API 返回了 GB/T → mismatch"""
        adapter = self.adapter
        adapter._do_request = MagicMock(return_value=self._fake_do_request(None))
        result = adapter._search("API 610 2004", target_code="API", target_number=610, target_year=2004)
        self.assertIsNotNone(result)
        self.assertNotEqual(result.match_status, "exact", "搜索 API 但 API 返回 GB/T → 不应该是 exact")

    def test_search_without_target_params_uses_empty(self):
        """不传目标参数时 match_result 收到空字符串 → 应返回非 exact"""
        adapter = self.adapter
        adapter._do_request = MagicMock(return_value=self._fake_do_request(None))
        result = adapter._search("API 610 2004")
        self.assertIsNotNone(result)
        # 空字符串代号 vs GB/T → 不应该是 exact
        self.assertNotEqual(result.match_status, "exact")

    def test_query_with_strategy_detects_mismatch(self):
        """query_with_strategy 用结构化参数匹配 API 返回，检测不匹配。"""
        adapter = self.adapter
        adapter._do_request = MagicMock(return_value=self._fake_do_request(None))
        result = adapter.query_with_strategy("API", 610, 2004)
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
        return {
            "code": code,
            "chName": ch_name,
            "status": Status.ACTIVE.value,
            "pk": "12345",
            "issueDate": 1293811200000,
            "actDate": 1293811200000,
            "chargeDept": "全国橡胶委",
        }

    def test_parse_result_with_matching_search_term(self):
        """search_term 与 API 结果匹配 → exact"""
        rec = self._make_rec("SH/T 1610-2011")
        result = self.adapter._parse_result(rec, "SH/T 1610-2011")
        self.assertEqual(result.match_status, "exact")

    def test_parse_result_with_mismatched_search_term(self):
        """search_term 与 API 结果不匹配 → 不应是 exact"""
        rec = self._make_rec("SH/T 1610-2011")
        result = self.adapter._parse_result(rec, "SH/T 1752-2006")
        self.assertNotEqual(
            result.match_status,
            "exact",
            "搜索 SH/T 1752 但 API 返回 SH/T 1610 → 不应该是 exact",
        )

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
        return {
            "code": code,
            "chName": ch_name,
            "status": Status.ACTIVE.value,
            "pk": "12345",
            "issueDate": 1577836800000,
            "actDate": 1577836800000,
            "chargeDept": "",
        }

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
        return {
            "STANDARD_NO": std_no,
            "ENGLISH_NAME": en_name,
            "STATE": Status.ACTIVE.value,
            "CIRCULATION_DATE": "2015-09-15",
            "STANDARD_STATUS": "ACTIVE",
            "YEAR_DATE": 2015,
            "PUBLISH_UNIT": "ISO",
            "id": "iso_9001",
        }

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
        self.assertFalse(adapter.can_handle(task), "空 source_site 不应被 openstd 适配器接受")

    def test_can_handle_accepts_openstd_download(self):
        """明确标记为 openstd_download 的任务应被接受。"""
        adapter = OpenstdDownloadAdapter()
        task = DownloadTask(standard_number="GB/T 1-2020", source_site="openstd_download")
        self.assertTrue(adapter.can_handle(task))

    def test_can_handle_rejects_foreign_site(self):
        """njbz365 / hbba 等非 openstd 站点不应被接受。"""
        adapter = OpenstdDownloadAdapter()
        for site in ("njbz365", "hbba", "dbba", "iso_gov", "csres"):
            task = DownloadTask(standard_number="API 610-2004", source_site=site)
            self.assertFalse(adapter.can_handle(task), f"site={site} 不应被 openstd 适配器接受")

    def test_find_adapter_maps_std_gov_to_openstd(self):
        """_QUERY_TO_DOWNLOAD_SITE 映射：std_gov → openstd_download"""
        adapter = OpenstdDownloadAdapter()
        engine = DownloadEngine(adapters=[adapter], session_manager=MagicMock())
        task = DownloadTask(standard_number="GB/T 19001-2016", source_site="std_gov")
        found = engine._find_adapter(task)
        self.assertIsNotNone(found, "std_gov 应通过映射找到 openstd_download 适配器")
        self.assertEqual(found.site_name, "openstd_download")

    def test_find_adapter_returns_none_for_foreign_standard(self):
        """国外标准（njbz365 等查询结果）→ 无下载适配器 → 返回 None"""
        adapter = OpenstdDownloadAdapter()
        engine = DownloadEngine(adapters=[adapter], session_manager=MagicMock())
        task = DownloadTask(standard_number="API 610-2004", source_site="njbz365")
        found = engine._find_adapter(task)
        self.assertIsNone(found, "njbz365 来源的国外标准不应有下载适配器，应返回清晰错误而非缺hcno")

    def test_download_task_accepts_source_site_param(self):
        """DownloadTask 可以接受 source_site 参数。"""
        task = DownloadTask(standard_number="GB/T 1-2020", source_site="std_gov")
        self.assertEqual(task.source_site, "std_gov")


# ════════════════════════════════════════════════════════════════
# 4b. 下载适配器按标准性质路由（2026-10-16 缺陷：国标只能被 std_gov 触发）
# ════════════════════════════════════════════════════════════════


class TestDownloadAdapterRoutingByStandardNature(unittest.TestCase):
    """`source_site` 是查询路由的产物，不能决定国标能否下载。

    现场实测（`http://192.168.1.18:9028`，2026-10-16）：`GB 2894-2025` 与
    `GB 2894-2008` 都落在 `cssn`，`is_downloadable=True`、`is_adopted=False`，
    但 `_find_adapter` 返回 None ⇒ "没有匹配的下载适配器"。
    """

    def _engine(self):
        return DownloadEngine(adapters=[OpenstdDownloadAdapter()], session_manager=MagicMock())

    def test_national_std_from_non_std_gov_site_is_routable(self):
        """国标落在 cssn（非 std_gov）也必须路由到 openstd_download。"""
        task = DownloadTask(standard_number="GB 2894-2025", source_site="cssn")
        found = self._engine()._find_adapter(task)
        self.assertIsNotNone(found, "cssn 来源的国标同样有下载适配器")
        self.assertEqual(found.site_name, "openstd_download")

    def test_slash_codes_are_routable(self):
        """GB/T、GB/Z 的代号解析保留斜杠，不能被判成非国标。"""
        for number in ("GB/T 1-2020", "GB/Z 184.1-2026", "GB 2894-2025", "GSB 1-2020"):
            with self.subTest(number=number):
                task = DownloadTask(standard_number=number, source_site="ahbz")
                found = self._engine()._find_adapter(task)
                self.assertIsNotNone(found, f"{number} 是 GB 类，应可路由")
                self.assertEqual(found.site_name, "openstd_download")

    def test_empty_source_site_national_std_still_routable(self):
        """查询未命中时 source_site 为空，国标仍应按性质路由。"""
        task = DownloadTask(standard_number="GB 2894-2025", source_site="")
        found = self._engine()._find_adapter(task)
        self.assertIsNotNone(found)
        self.assertEqual(found.site_name, "openstd_download")

    def test_non_national_std_still_has_no_adapter(self):
        """非国标（行业/国外）不得因为本修复而变成可下载。"""
        for site, number in (("hbba", "AQ/T 9007-2019"), ("njbz365", "API 610-2004"), ("csres", "HJ 1234-2020")):
            with self.subTest(number=number):
                self.assertIsNone(self._engine()._find_adapter(DownloadTask(standard_number=number, source_site=site)))

    def test_unregistered_openstd_falls_through_to_can_handle(self):
        """openstd 未注册时，国标分支必须继续走 can_handle 兜底，不能直接短路成 None。"""

        class AnyAdapter(OpenstdDownloadAdapter):
            @property
            def site_name(self):
                return "other_download"

            def can_handle(self, task):
                return True

        engine = DownloadEngine(adapters=[AnyAdapter()], session_manager=MagicMock())
        task = DownloadTask(standard_number="GB 2894-2025", source_site="cssn")
        found = engine._find_adapter(task)
        self.assertIsNotNone(found)
        self.assertEqual(found.site_name, "other_download")

    def test_explicit_site_still_wins(self):
        """显式指定/映射表优先于标准性质（保留手工与收藏链的既有口径）。"""
        task = DownloadTask(standard_number="GB 2894-2025", source_site="openstd_download")
        found = self._engine()._find_adapter(task)
        self.assertEqual(found.site_name, "openstd_download")

        mapped = DownloadTask(standard_number="GB 2894-2025", source_site="std_gov")
        self.assertEqual(self._engine()._find_adapter(mapped).site_name, "openstd_download")


class TestNoAdapterErrorMessage(unittest.TestCase):
    """无适配器时的错误信息必须可诊断，区分"非国标"与"国标但适配器未注册"。"""

    def _engine(self):
        return DownloadEngine(adapters=[OpenstdDownloadAdapter()], session_manager=MagicMock())

    def test_non_national_std_message_names_code_and_site(self):
        task = DownloadTask(standard_number="AQ/T 9007-2019", source_site="hbba")
        task = self._engine().download_single(task)
        self.assertEqual(task.status, DownloadStatus.FAILED)
        self.assertIn("非国标", task.error_message)
        self.assertIn("AQ/T", task.error_message)
        self.assertIn("hbba", task.error_message)

    def test_national_std_message_when_adapter_missing(self):
        engine = DownloadEngine(adapters=[], session_manager=MagicMock())
        task = DownloadTask(standard_number="GB 2894-2025", source_site="cssn")
        task = engine.download_single(task)
        self.assertEqual(task.status, DownloadStatus.FAILED)
        self.assertIn("GB", task.error_message)
        self.assertIn("cssn", task.error_message)

    def test_fetch_bytes_uses_same_message(self):
        task = DownloadTask(standard_number="AQ/T 9007-2019", source_site="hbba")
        content, err = self._engine().fetch_bytes(task)
        self.assertIsNone(content)
        self.assertIn("非国标", err)
        self.assertIn("hbba", err)


# ════════════════════════════════════════════════════════════════
# 5. ParsedStdInfo found_source_site 字段
# ════════════════════════════════════════════════════════════════


class TestFoundSourceSiteField(unittest.TestCase):
    """验证 ParsedStdInfo 新增的 found_source_site 字段。"""

    def test_field_exists_with_default(self):
        from pilotstd.models import ParsedStdInfo

        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB/T", number=1, year=2020)
        self.assertEqual(p.found_source_site, "")

    def test_field_can_be_set(self):
        from pilotstd.models import ParsedStdInfo

        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB/T", number=1, year=2020)
        p.found_source_site = "std_gov"
        self.assertEqual(p.found_source_site, "std_gov")


if __name__ == "__main__":
    unittest.main()
