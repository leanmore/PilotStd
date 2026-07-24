# tests/test_gongbiaoku.py
"""工标库适配器单元测试（100% mock）。"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from bs4 import BeautifulSoup

from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestGongBiaoKuAdapter(unittest.TestCase):
    """工标库适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.gongbiaoku import GongBiaoKuAdapter

        self.a = GongBiaoKuAdapter()

    # ── _parse_ul 单元测试 ──

    def test_parse_ul_from_fixture(self):
        """从真实 fixture 解析标准。"""
        fixture = FIXTURE_DIR / "gongbiaoku_free_list.html"
        if not fixture.exists():
            self.skipTest("Fixture not found: run Task 0 first.")
        html = fixture.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        uls = soup.select("ul.name-intr")
        self.assertGreaterEqual(len(uls), 1)
        r = self.a._parse_ul(uls[0], "GB")
        self.assertIsNotNone(r)
        self.assertIsInstance(r, QueryResult)
        self.assertTrue(r.standard_number.startswith("GB"))
        self.assertTrue(r.standard_name)
        self.assertTrue(r.publish_date)
        self.assertTrue(r.implementation_date)
        self.assertEqual(r.status, "现行")

    def test_parse_ul_all_fields(self):
        """4-li 分组所有字段正确提取。"""
        html = """<ul class="name-intr">
            <li>标准名称： 测试标准规范</li>
            <li>标准编号： GB 12345-2020</li>
            <li>发布日期： 2020-01-01</li>
            <li>实施日期： 2020-07-01</li>
        </ul>"""
        soup = BeautifulSoup(html, "html.parser")
        ul = soup.select_one("ul.name-intr")
        r = self.a._parse_ul(ul, "GB 12345")
        self.assertIsNotNone(r)
        self.assertEqual(r.standard_number, "GB 12345-2020")
        self.assertEqual(r.standard_name, "测试标准规范")
        self.assertEqual(r.publish_date, "2020-01-01")
        self.assertEqual(r.implementation_date, "2020-07-01")
        self.assertEqual(r.source_site, "gongbiaoku")

    def test_parse_ul_partial_fields(self):
        """部分字段缺失时仍能返回结果。"""
        html = """<ul class="name-intr">
            <li>标准名称： 测试标准</li>
            <li>标准编号： GB/T 99999-2099</li>
        </ul>"""
        soup = BeautifulSoup(html, "html.parser")
        ul = soup.select_one("ul.name-intr")
        r = self.a._parse_ul(ul, "")
        self.assertIsNotNone(r)
        self.assertEqual(r.standard_number, "GB/T 99999-2099")
        self.assertEqual(r.publish_date, "")

    def test_parse_ul_empty(self):
        """空 ul 返回 None。"""
        html = "<ul class='name-intr'></ul>"
        soup = BeautifulSoup(html, "html.parser")
        ul = soup.select_one("ul.name-intr")
        self.assertIsNone(self.a._parse_ul(ul, ""))

    # ── _search 单元测试 ──

    def test_search_returns_result(self):
        """搜索返回 QueryResult。"""
        fixture = FIXTURE_DIR / "gongbiaoku_free_list.html"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        html = fixture.read_text(encoding="utf-8")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        self.a._client.get = MagicMock(return_value=mock_resp)
        r = self.a._search("GB")
        self.assertIsNotNone(r)
        self.assertIsInstance(r, QueryResult)

    def test_search_no_results(self):
        """无结果返回 None。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body></body></html>"
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.assertIsNone(self.a._search("NONEXISTENT"))

    def test_search_network_error(self):
        """网络异常返回 None。"""
        self.a._client.get = MagicMock(side_effect=Exception("timeout"))
        self.assertIsNone(self.a._search("GB"))

    # ── query_standards 集成测试 ──

    def test_query_standards_returns_list(self):
        """返回 list[QueryResult]。"""
        fixture = FIXTURE_DIR / "gongbiaoku_free_list.html"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        html = fixture.read_text(encoding="utf-8")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        self.a._client.get = MagicMock(return_value=mock_resp)
        results = self.a.query_standards("GB")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r, QueryResult)

    def test_query_standards_empty_keyword(self):
        """空关键词返回空列表。"""
        self.assertEqual(self.a.query_standards(""), [])


if __name__ == "__main__":
    unittest.main()
