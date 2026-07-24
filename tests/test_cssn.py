# tests/test_cssn.py
"""中国标准服务网适配器单元测试（100% mock）。"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestCSSNAdapter(unittest.TestCase):
    """中国标准服务网适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.cssn import CSSNAdapter

        self.a = CSSNAdapter()

    # ── _parse_result ──

    def test_parse_result_from_fixture(self):
        fixture = FIXTURE_DIR / "cssn_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        result = self.a._parse_result(row, "GB/T")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "GB/T 35081-2018")
        self.assertEqual(result.standard_name, "机械安全 GB/T 16855.1与GB/T 15706的关系")
        self.assertEqual(result.status, "现行")
        self.assertEqual(result.publish_date, "2018-05-14")
        self.assertEqual(result.implementation_date, "2018-12-01")
        self.assertEqual(result.source_site, "cssn")

    def test_dynamic_attributes(self):
        """动态属性 standard_type/ccs/ics 正确设置。"""
        fixture = FIXTURE_DIR / "cssn_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        result = self.a._parse_result(row, "GB/T")
        self.assertEqual(getattr(result, "standard_type", ""), "国家标准")
        self.assertEqual(getattr(result, "ccs", ""), "卫生、安全、劳动保护")
        self.assertEqual(getattr(result, "ics", ""), "机械安全")

    def test_parse_result_empty(self):
        result = self.a._parse_result({}, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "")

    # ── query_standards 分页 ──

    def test_query_standards_page_param(self):
        """page=2 时请求参数含 page=2。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"count": 0, "next": None, "results": []})
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.a.query_standards("GB/T", page=2, max_pages=1)
        call_params = self.a._client.get.call_args[1]["params"]
        self.assertEqual(call_params["page"], 2)

    def test_query_standards_stops_on_no_next(self):
        """next=None 时不再翻第 2 页。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(
            return_value={
                "count": 5,
                "next": None,
                "results": [{"a100": "GB/T 1.1-2020", "a298": "标准化工作导则", "a000": "现行"}],
            }
        )
        self.a._client.get = MagicMock(return_value=mock_resp)
        results = self.a.query_standards("GB/T", max_pages=5)
        self.assertEqual(self.a._client.get.call_count, 1)
        self.assertEqual(len(results), 1)

    def test_query_standards_multipage(self):
        """next 存在时继续翻页，next=None 时停止。"""
        page1 = MagicMock()
        page1.status_code = 200
        page1.json = MagicMock(
            return_value={
                "count": 40,
                "next": "/standards/?page=2",
                "results": [{"a100": f"GB/T {i}-2020", "a298": f"标准{i}", "a000": "现行"} for i in range(20)],
            }
        )
        page2 = MagicMock()
        page2.status_code = 200
        page2.json = MagicMock(
            return_value={
                "count": 40,
                "next": None,
                "results": [{"a100": f"GB/T {i}-2020", "a298": f"标准{i}", "a000": "现行"} for i in range(20, 40)],
            }
        )
        self.a._client.get = MagicMock(side_effect=[page1, page2])
        results = self.a.query_standards("GB/T", max_pages=3)
        self.assertEqual(self.a._client.get.call_count, 2)
        self.assertEqual(len(results), 40)

    # ── _search_candidates ──

    def test_search_candidates_returns_list(self):
        fixture = FIXTURE_DIR / "cssn_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found")
        row = json.loads(fixture.read_text(encoding="utf-8"))
        payload = {"count": 1, "next": None, "results": [row]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.get = MagicMock(return_value=mock_resp)
        results = self.a._search_candidates("GB/T")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], QueryResult)

    def test_search_candidates_no_results(self):
        payload = {"count": 0, "next": None, "results": []}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("NONEXISTENT"), [])

    def test_search_candidates_network_error(self):
        self.a._client.get = MagicMock(side_effect=Exception("timeout"))
        self.assertEqual(self.a._search_candidates("GB/T"), [])

    def test_query_standards_empty_keyword(self):
        self.assertEqual(self.a.query_standards(""), [])

    # ── count 上限告警 ──

    def test_count_warning_at_10000(self):
        payload = {"count": 10000, "next": None, "results": [{"a100": "GB/T 1-2020", "a298": "测试", "a000": "现行"}]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=payload)
        self.a._client.get = MagicMock(return_value=mock_resp)
        with self.assertLogs("pilotstd.query.adapters.cssn", level="WARNING") as log_ctx:
            self.a._search_candidates("GB/T")
            self.assertTrue(any("10000" in msg for msg in log_ctx.output))


if __name__ == "__main__":
    unittest.main()
