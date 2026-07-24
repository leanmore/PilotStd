# tests/test_energy.py
"""能源标准适配器单元测试（100% mock）。"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestEnergyAdapter(unittest.TestCase):
    """能源标准适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.energy import EnergyAdapter

        self.a = EnergyAdapter()

    # ── _parse_result 单元测试 ──

    def test_parse_result_from_fixture(self):
        """从 JSON fixture 解析标准记录。"""
        fixture = FIXTURE_DIR / "energy_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        rec = data["rows"][0]
        result = self.a._parse_result(rec, "NB")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, QueryResult)
        self.assertTrue(result.standard_number.startswith("NB"))
        self.assertTrue(result.standard_name)
        self.assertEqual(result.source_site, "energy")
        self.assertEqual(result.status, "现行")

    def test_parse_result_maps_fields(self):
        """JSON 字段全部正确映射。"""
        rec = {
            "stdCode": "NB/T 10456-2021",
            "stdId": 10001,
            "replacedStd": "NB/T 10456-2015",
            "stdName": "能源管理系统技术规范",
            "state": "现行",
            "issueDate": "2021-07-01",
            "actDate": "2021-10-01",
        }
        result = self.a._parse_result(rec, "NB")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "NB/T 10456-2021")
        self.assertEqual(result.standard_name, "能源管理系统技术规范")
        self.assertEqual(result.status, "现行")
        self.assertEqual(result.publish_date, "2021-07-01")
        self.assertEqual(result.implementation_date, "2021-10-01")
        self.assertEqual(result.replaces, "NB/T 10456-2015")
        self.assertEqual(result.hcno, "10001")

    def test_parse_result_partial_fields(self):
        """部分字段缺失时仍能返回结果。"""
        rec = {"stdCode": "GB/T 99999-2099", "stdName": "测试标准"}
        result = self.a._parse_result(rec, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "GB/T 99999-2099")
        self.assertEqual(result.publish_date, "")
        self.assertEqual(result.replaces, "")

    def test_parse_result_empty(self):
        """空记录返回 QueryResult（含空字段）。"""
        result = self.a._parse_result({}, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "")

    # ── _search_candidates 单元测试 ──

    def test_search_candidates_returns_list(self):
        """搜索返回 list[QueryResult]。"""
        fixture = FIXTURE_DIR / "energy_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=data)
        self.a._client.get = MagicMock(return_value=mock_resp)
        results = self.a._search_candidates("NB")
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
        self.assertEqual(self.a._search_candidates("NB"), [])

    def test_search_candidates_non_200(self):
        """非 200 状态码返回空列表。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        self.a._client.get = MagicMock(return_value=mock_resp)
        self.assertEqual(self.a._search_candidates("NB"), [])

    # ── query_standards 集成测试 ──

    def test_query_standards_returns_list(self):
        """返回 list[QueryResult]。"""
        fixture = FIXTURE_DIR / "energy_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=data)
        self.a._client.get = MagicMock(return_value=mock_resp)
        results = self.a.query_standards("NB")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_query_standards_empty_keyword(self):
        """空关键词返回空列表。"""
        self.assertEqual(self.a.query_standards(""), [])

    # ── Host Header 显式声明 ──

    def test_host_header_explicit(self):
        """纯IP站点：默认客户端必须显式声明 Host Header。"""
        from pilotstd.query.adapters.energy import EnergyAdapter

        a = EnergyAdapter()
        self.assertEqual(a._client.headers["Host"], "114.251.111.103:18080")
        self.assertEqual(a._client.headers["Referer"], "https://114.251.111.103:18080/zxd/portal/std")
        self.assertEqual(a._client.headers["X-Requested-With"], "XMLHttpRequest")

    def test_host_header_preserved_with_custom_client(self):
        """注入自定义客户端后 Host Header 不受影响。"""
        from pilotstd.query.adapters.energy import EnergyAdapter

        custom = httpx.Client(headers={"X-Custom": "test"})
        a = EnergyAdapter(client=custom)
        self.assertEqual(a._client, custom)
        self.assertEqual(a._client.headers["X-Custom"], "test")

    # ── 年份回退 ──

    def test_year_fallback(self):
        """含年份无结果时自动去年份宽搜。"""
        fixture = FIXTURE_DIR / "energy_sample.json"
        if not fixture.exists():
            self.skipTest("Fixture not found.")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.json = MagicMock(return_value={"total": 0, "rows": []})
        data_resp = MagicMock()
        data_resp.status_code = 200
        data_resp.json = MagicMock(return_value=data)
        # 第一次含年份搜索返回空，第二次去年份返回结果
        self.a._client.get = MagicMock(side_effect=[empty_resp, data_resp])
        results = self.a._search_candidates("NB/T 10456-2021")
        self.assertEqual(len(results), 3)
        self.assertEqual(self.a._client.get.call_count, 2)

    # ── 分页兜底 ──

    def test_pagination_warning(self):
        """total > len(rows) 时发出 warning 日志。"""
        overflow_data = {"total": 50, "rows": [{"stdCode": "NB/T 10456-2021", "stdName": "测试"}]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=overflow_data)
        self.a._client.get = MagicMock(return_value=mock_resp)
        with patch("pilotstd.query.adapters.energy.logger.warning") as mock_warn:
            results = self.a._search_candidates("NB")
            self.assertEqual(len(results), 1)
            mock_warn.assert_called_once()
            # logger.warning(msg, total, limit, len_rows) → args[0] 是 msg，args[1:] 是参数
            self.assertEqual(mock_warn.call_args[0][1], 50)
            self.assertEqual(mock_warn.call_args[0][2], 15)
            self.assertEqual(mock_warn.call_args[0][3], 1)


if __name__ == "__main__":
    unittest.main()
