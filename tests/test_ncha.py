# tests/test_ncha.py
"""文物保护标准适配器单元测试（100% mock）。"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestNCHAAdapter(unittest.TestCase):
    """文物保护标准适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.ncha import NCHAAdapter

        self.a = NCHAAdapter()

    # ── _format_date ──

    def test_format_date_with_time(self):
        from pilotstd.query.adapters.ncha import _format_date

        self.assertEqual(_format_date("2023/12/6 0:00"), "2023-12-06")

    def test_format_date_without_time(self):
        from pilotstd.query.adapters.ncha import _format_date

        self.assertEqual(_format_date("2023/12/6"), "2023-12-06")

    def test_format_date_already_iso(self):
        from pilotstd.query.adapters.ncha import _format_date

        self.assertEqual(_format_date("2023-12-06"), "2023-12-06")

    def test_format_date_empty(self):
        from pilotstd.query.adapters.ncha import _format_date

        self.assertEqual(_format_date(""), "")

    def test_format_date_none(self):
        from pilotstd.query.adapters.ncha import _format_date

        self.assertEqual(_format_date(None), "")

    # ── _parse_result ──

    def test_parse_result_wwt(self):
        fixture = FIXTURE_DIR / "ncha_wwt_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        result = self.a._parse_result(row, "WW/T")
        self.assertIsNotNone(result)
        self.assertTrue(result.standard_number.startswith("WW/T"))
        self.assertEqual(result.standard_name, "馆藏文物保存环境监测 监测终端安装要求")
        self.assertEqual(result.status, "现行")
        self.assertEqual(result.publish_date, "2023-12-06")
        self.assertEqual(result.implementation_date, "2024-07-01")
        self.assertEqual(result.responsible_dept, "国家文物局")
        self.assertEqual(result.hcno, "W118")
        self.assertEqual(result.source_site, "ncha")

    def test_parse_result_gbt(self):
        fixture = FIXTURE_DIR / "ncha_gbt_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        result = self.a._parse_result(row, "GB/T")
        self.assertIsNotNone(result)
        self.assertTrue(result.standard_number.startswith("GB/T"))
        self.assertEqual(result.status, "现行")
        self.assertEqual(result.publish_date, "2024-09-29")

    def test_parse_result_empty(self):
        result = self.a._parse_result({}, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "")

    # ── _build_body ──

    def test_build_body_contains_keyword(self):
        body = self.a._build_body("WW/T")
        self.assertEqual(body["condition"]["keyword"], "WW/T")
        self.assertEqual(body["pagination"]["currentPage"], 1)
        self.assertEqual(body["pagination"]["pageSize"], 20)
        self.assertEqual(body["sort"]["column"], "publishingDate")

    # ── _search_candidates ──

    def test_search_candidates_wwt(self):
        fixture = FIXTURE_DIR / "ncha_wwt_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        payload = {"code": 200, "data": {"pagination": {"totalNum": 1}, "data": [row]}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        results = self.a._search_candidates("WW/T")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], QueryResult)

    def test_search_candidates_api_error_code(self):
        payload = {"code": 500, "msg": "查看失败", "data": None}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("WW/T"), [])

    def test_search_candidates_no_results(self):
        payload = {"code": 200, "data": {"pagination": {"totalNum": 0}, "data": []}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("NONEXISTENT"), [])

    def test_search_candidates_network_error(self):
        self.a._client.post = MagicMock(side_effect=Exception("timeout"))
        self.assertEqual(self.a._search_candidates("WW/T"), [])

    def test_search_candidates_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        self.a._client.post = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("WW/T"), [])

    # ── query_standards ──

    def test_query_standards_empty_keyword(self):
        self.assertEqual(self.a.query_standards(""), [])

    def test_query_standards_returns_list(self):
        fixture = FIXTURE_DIR / "ncha_wwt_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        payload = {"code": 200, "data": {"pagination": {"totalNum": 1}, "data": [row]}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        results = self.a.query_standards("WW/T")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()
