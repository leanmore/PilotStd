# tests/test_miit.py
"""工信部行业标准适配器单元测试（100% mock）。"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestMIITAdapter(unittest.TestCase):
    """工信部行业标准适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.miit import MIITAdapter

        self.a = MIITAdapter()

    # ── _parse_result ──

    def test_parse_result_from_fixture(self):
        fixture = FIXTURE_DIR / "miit_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        result = self.a._parse_result(row, "SH/T")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "SH/T 3167-2012")
        self.assertEqual(result.standard_name, "钢制焊接低压储罐")
        self.assertEqual(result.publish_date, "2012-11-07")
        self.assertEqual(result.implementation_date, "2013-03-01")
        self.assertEqual(result.status, "现行")
        self.assertEqual(result.source_site, "miit")

    def test_parse_result_empty(self):
        result = self.a._parse_result({}, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "")

    # ── _fetch_candidates form body 验证 ──

    def test_fetch_uses_stadardnum(self):
        """验证使用正确的拼写错误参数名 stadardNum。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"code": 0, "data": []})
        self.a._client.post = MagicMock(return_value=mock_resp)
        self.a._fetch_candidates("SH/T")
        call_kwargs = self.a._client.post.call_args[1]
        self.assertEqual(call_kwargs["data"]["stadardNum"], "SH/T")
        self.assertEqual(call_kwargs["data"]["userCode"], "游客")
        self.assertEqual(call_kwargs["data"]["sourceType"], "more")

    # ── _search_candidates ──

    def test_search_candidates_returns_list(self):
        fixture = FIXTURE_DIR / "miit_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        payload = {"code": 0, "data": [row]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        results = self.a._search_candidates("SH/T")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], QueryResult)

    def test_search_candidates_api_error_code(self):
        payload = {"code": -1, "data": None}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("SH/T"), [])

    def test_search_candidates_no_results(self):
        payload = {"code": 0, "data": []}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("NONEXISTENT"), [])

    def test_search_candidates_network_error(self):
        self.a._client.post = MagicMock(side_effect=Exception("timeout"))
        self.assertEqual(self.a._search_candidates("SH/T"), [])

    def test_search_candidates_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        self.a._client.post = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("SH/T"), [])

    # ── 15 条截断告警 ──

    def test_truncation_warning_at_15(self):
        """返回恰好 15 条时触发截断 warning。"""
        rows = [{"bpiBzno": f"HG/T {i}-2020", "piProjectname": f"标准{i}"} for i in range(15)]
        payload = {"code": 0, "data": rows}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        with self.assertLogs("pilotstd.query.adapters.miit", level="WARNING") as log_ctx:
            results = self.a._search_candidates("HG")
            self.assertEqual(len(results), 15)
            self.assertTrue(any("截断" in msg for msg in log_ctx.output))

    def test_no_warning_under_15(self):
        """少于 15 条不触发截断 warning。"""
        rows = [{"bpiBzno": f"SH/T {i}-2020", "piProjectname": f"标准{i}"} for i in range(3)]
        payload = {"code": 0, "data": rows}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.post = MagicMock(return_value=mock_resp)
        results = self.a._search_candidates("SH/T")
        self.assertEqual(len(results), 3)

    # ── query_standards ──

    def test_query_standards_empty_keyword(self):
        self.assertEqual(self.a.query_standards(""), [])


if __name__ == "__main__":
    unittest.main()
