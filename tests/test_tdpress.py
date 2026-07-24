# tests/test_tdpress.py
"""铁路标准适配器单元测试（100% mock）。"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestTDPressAdapter(unittest.TestCase):
    """铁路标准适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.tdpress import TDPressAdapter

        self.a = TDPressAdapter()

    # ── _safe_ts_to_date ──

    def test_timestamp_conversion_valid(self):
        from pilotstd.query.adapters.tdpress import _safe_ts_to_date

        self.assertEqual(_safe_ts_to_date(1422720000000), "2015-02-01")

    def test_timestamp_conversion_null(self):
        from pilotstd.query.adapters.tdpress import _safe_ts_to_date

        self.assertEqual(_safe_ts_to_date(None), "")

    def test_timestamp_conversion_invalid(self):
        from pilotstd.query.adapters.tdpress import _safe_ts_to_date

        # 非数字类型返回空字符串
        self.assertEqual(_safe_ts_to_date("not_a_number"), "")

    def test_timestamp_cst_boundary(self):
        """UTC 23:59:59 → CST 次日 07:59:59，显式时区确保日期不偏移。"""
        from pilotstd.query.adapters.tdpress import _safe_ts_to_date

        # 1422748799000 ms = 2015-01-31 23:59:59 UTC = 2015-02-01 07:59:59 CST
        self.assertEqual(_safe_ts_to_date(1422748799000), "2015-02-01")

    # ── _map_status ──

    def test_status_mapping_known(self):
        from pilotstd.query.adapters.tdpress import _map_status

        self.assertEqual(_map_status("TRUE"), "现行")
        self.assertEqual(_map_status("FALSE"), "废止")

    def test_status_mapping_unknown_preserved(self):
        from pilotstd.query.adapters.tdpress import _map_status

        self.assertEqual(_map_status("REVIEWING"), "REVIEWING")

    def test_status_mapping_empty(self):
        from pilotstd.query.adapters.tdpress import _map_status

        self.assertEqual(_map_status(""), "")

    # ── _parse_result ──

    def test_field_mapping(self):
        """JSON 字段全部正确映射。"""
        rec = {
            "standardNumber": "TB 10621-2014",
            "standardName": "高速铁路设计规范",
            "standardStatus": "FALSE",
            "replaceStandard": "TB 10621-2009",
            "implementDate": 1422720000000,
            "publicationDate": 1417363200000,
            "supervisorDept": "国家铁路局",
            "standardFilingNum": "J 1942-2014",
        }
        result = self.a._parse_result(rec, "TB")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "TB 10621-2014")
        self.assertEqual(result.standard_name, "高速铁路设计规范")
        self.assertEqual(result.status, "废止")
        self.assertEqual(result.replaces, "TB 10621-2009")
        self.assertEqual(result.implementation_date, "2015-02-01")
        self.assertEqual(result.publish_date, "2014-12-01")
        self.assertEqual(result.responsible_dept, "国家铁路局")
        self.assertEqual(result.hcno, "J 1942-2014")
        self.assertEqual(result.source_site, "tdpress")

    def test_field_mapping_minimal(self):
        """最小字段时仍返回有效 QueryResult。"""
        rec = {"standardNumber": "TB 10621-2014", "standardName": "高速铁路设计规范"}
        result = self.a._parse_result(rec, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "TB 10621-2014")
        self.assertEqual(result.status, "")
        self.assertEqual(result.replaces, "")

    # ── _search_candidates ──

    def test_search_candidates_returns_list(self):
        """搜索返回 list[QueryResult]。"""
        fixture = FIXTURE_DIR / "tdpress_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=data)
        self.a._client.get = MagicMock(return_value=mock_resp)
        results = self.a._search_candidates("TB")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r, QueryResult)

    def test_search_candidates_no_results(self):
        """无结果返回空列表。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"total": 0, "rows": []})
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("NONEXISTENT"), [])

    def test_search_candidates_network_error(self):
        """网络异常返回空列表。"""
        self.a._client.get = MagicMock(side_effect=Exception("timeout"))
        self.assertEqual(self.a._search_candidates("TB"), [])

    def test_search_candidates_non_200(self):
        """非 200 返回空列表。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("TB"), [])

    def test_search_candidates_json_error(self):
        """JSON 解析失败返回空列表。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(side_effect=ValueError("bad json"))
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("TB"), [])

    # ── query_standards ──

    def test_query_standards_empty_keyword(self):
        """空关键词返回空列表。"""
        self.assertEqual(self.a.query_standards(""), [])

    # ── Host Header ──

    def test_default_client_headers(self):
        """默认客户端包含必要请求头。"""
        from pilotstd.query.adapters.tdpress import TDPressAdapter

        a = TDPressAdapter()
        self.assertEqual(a._client.headers["X-Requested-With"], "XMLHttpRequest")
        self.assertIn("tdpress.com", a._client.headers["Referer"])

    # ── soleLogo 默认值 ──

    def test_solelogo_default_tlbz(self):
        """搜索参数默认 soleLogo=tlbz。"""
        fixture = FIXTURE_DIR / "tdpress_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=data)
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.a._search_candidates("TB")
        call_args = self.a._client.get.call_args
        self.assertIn("params", call_args[1])
        self.assertEqual(call_args[1]["params"]["soleLogo"], "tlbz")


if __name__ == "__main__":
    unittest.main()
