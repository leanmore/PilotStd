# tests/test_energy_pagination.py
"""能源标准适配器：翻页 / fallback / 解析失败分支（此前无用例，P2 B2 补齐）。

背景（`docs/plans/2026-11-24-p2-recon-existing.md`）：
- 现有 `tests/test_energy.py` 的 fixture `total=3` 从不进第 2 页 ⇒ 多页成功路径无覆盖；
- `fallback` 成功路径、JSON 解析失败路径也无用例；
- 冒烟脚本曾引用不存在的 `adapter.API_URL` 必崩（已修），本文件不复现该缺陷。
"""

import unittest
from unittest.mock import MagicMock

from pilotstd.query.models import QueryResult


def _row(i: int) -> dict:
    return {
        "stdCode": f"NB/T {40000 + i}-2026",
        "stdId": 100000 + i,
        "replacedStd": None,
        "stdName": f"测试标准 {i}",
        "state": "现行",
        "issueDate": "2026-01-01",
        "actDate": "2026-07-01",
    }


def _resp(payload, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=payload)
    return resp


class TestEnergyPagination(unittest.TestCase):
    def setUp(self):
        from pilotstd.query.adapters.energy import EnergyAdapter

        self.a = EnergyAdapter()

    def test_second_page_fetched_when_total_exceeds_page_size(self):
        """首页 15 条且 total=20 → 继续拉第 2 页并合并。"""
        page1 = {"total": 20, "rows": [_row(i) for i in range(15)]}
        page2 = {"total": 20, "rows": [_row(i) for i in range(15, 20)]}
        self.a._client.get = MagicMock(side_effect=[_resp(page1), _resp(page2)])
        results = self.a._search_candidates("NB/T")
        self.assertEqual(len(results), 20)
        self.assertEqual(self.a._client.get.call_count, 2)
        self.assertTrue(all(isinstance(r, QueryResult) for r in results))

    def test_single_page_when_total_within_page_size(self):
        """total ≤ PAGE_SIZE → 不翻页。"""
        payload = {"total": 3, "rows": [_row(i) for i in range(3)]}
        self.a._client.get = MagicMock(return_value=_resp(payload))
        results = self.a._search_candidates("NB/T 1")
        self.assertEqual(len(results), 3)
        self.assertEqual(self.a._client.get.call_count, 1)

    def test_partial_page_stops(self):
        """返回条数 < PAGE_SIZE → 视为末页，不再翻页。"""
        page1 = {"total": 100, "rows": [_row(i) for i in range(5)]}
        self.a._client.get = MagicMock(return_value=_resp(page1))
        self.a._search_candidates("NB/T 2")
        self.assertEqual(self.a._client.get.call_count, 1)


class TestEnergyFallback(unittest.TestCase):
    def setUp(self):
        from pilotstd.query.adapters.energy import EnergyAdapter

        self.a = EnergyAdapter()

    def test_http_fallback_used_when_https_fails(self):
        """主地址异常 → 同主机 HTTP 降级成功，结果返回。"""
        ok = _resp({"total": 1, "rows": [_row(0)]})
        self.a._client.get = MagicMock(side_effect=[RuntimeError("tls failed"), ok])
        results = self.a._search_candidates("NB/T 3")
        self.assertEqual(len(results), 1)
        self.assertEqual(self.a._client.get.call_count, 2)
        second_url = self.a._client.get.call_args_list[1].args[0]
        self.assertTrue(second_url.startswith("http://"), f"fallback 应为 HTTP: {second_url}")

    def test_no_unverified_domain_in_fallback(self):
        """未实测的域名 fallback 已删除：fallback 只会出现同主机的 HTTP 降级。"""
        ok = _resp({"total": 1, "rows": [_row(0)]})
        self.a._client.get = MagicMock(side_effect=[RuntimeError("boom"), ok])
        self.a._search_candidates("NB/T 4")
        urls = [c.args[0] for c in self.a._client.get.call_args_list]
        self.assertFalse(any("nbse.org.cn" in u for u in urls), f"出现未验证域名: {urls}")

    def test_all_urls_fail_returns_empty(self):
        self.a._client.get = MagicMock(side_effect=[RuntimeError("a"), RuntimeError("b")])
        self.assertEqual(self.a._search_candidates("NB/T 5"), [])


class TestEnergyParseFailure(unittest.TestCase):
    def setUp(self):
        from pilotstd.query.adapters.energy import EnergyAdapter

        self.a = EnergyAdapter()

    def test_json_parse_failure_returns_empty(self):
        """站点返回 HTML 错误页（JSON 解析失败）→ 空结果，不抛异常。"""
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(side_effect=ValueError("expecting value"))
        self.a._client.get = MagicMock(return_value=resp)
        self.assertEqual(self.a._search_candidates("NB/T 6"), [])

    def test_non_200_first_page_returns_empty(self):
        self.a._client.get = MagicMock(return_value=_resp(None, status=500))
        self.assertEqual(self.a._search_candidates("NB/T 7"), [])

    def test_year_stripped_retry(self):
        """带年份无结果 → 自动去年份宽搜。"""
        empty = _resp({"total": 0, "rows": []})
        hit = _resp({"total": 1, "rows": [_row(0)]})
        self.a._client.get = MagicMock(side_effect=[empty, hit])
        results = self.a._search_candidates("NB/T 47016-2023")
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
