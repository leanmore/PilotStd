# tests/test_ttbz.py
"""团体标准平台（ttbz）适配器回归测试（100% mock，真实响应 fixture）。

真实样本见 `tests/fixtures/ttbz_sample.json`（2026-11-24 从
`POST /cms-proxy/ms/portal/standardInfo/getPortalStandardList` 实测冻结）。

覆盖 2026-11-24 修复的三个真实缺陷：
1. **参数用错**：按标准号检索必须用 `standardNo`；`standardName` 是名称过滤（用号码搜恒 0 条）；
2. **缺会话引导**：直接 POST 接口返回 403「访问受限」，需先访问 `standard.html` 拿 JSESSIONID；
3. **字段缺映射**：真实响应含 `abolishDate`，此前未映射到 `abolition_date`。
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pilotstd.core.status import Status
from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture() -> dict:
    return json.loads((FIXTURE_DIR / "ttbz_sample.json").read_text(encoding="utf-8"))


class TestSearchRequest(unittest.TestCase):
    """检索参数与会话引导。"""

    def setUp(self):
        from pilotstd.query.adapters.ttbz import TTBZAdapter

        self.a = TTBZAdapter()

    def _resp(self, body: dict, status: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.json = MagicMock(return_value=body)
        return resp

    def test_query_uses_standard_no(self):
        """按标准号检索必须传 `standardNo`（原缺陷：传 `standardName` → 0 条）。"""
        payload = {"code": 200, "data": {"total": 1, "rows": _fixture()["rows"][:1]}}
        with patch("pilotstd.query.adapters.ttbz.safe_post", return_value=self._resp(payload)) as post:
            self.a.query_standards("T/BSCA 0006—2026")
        data = post.call_args.kwargs["data"]
        self.assertEqual(data["standardNo"], "T/BSCA 0006—2026")
        self.assertNotIn("standardName", data)

    def test_build_search_data_uses_standard_no(self):
        data = self.a._build_search_data("T/CECS 100")
        self.assertEqual(data["standardNo"], "T/CECS 100")
        self.assertNotIn("standardName", data)

    def test_session_bootstrap_runs_once(self):
        """首次请求前 GET 标准页引导会话；已引导则不重复。"""
        self.a._session.get = MagicMock(return_value=MagicMock(status_code=200))
        self.a._ensure_session()
        self.a._ensure_session()
        self.assertEqual(self.a._session.get.call_count, 1)
        self.assertIn("standard.html", self.a._session.get.call_args.args[0])

    def test_session_bootstrap_failure_does_not_raise(self):
        self.a._session.get = MagicMock(side_effect=RuntimeError("timeout"))
        self.a._ensure_session()  # 不抛
        self.assertTrue(self.a._session_ready)


class TestParseResult(unittest.TestCase):
    """字段映射（真实 fixture）。"""

    def setUp(self):
        from pilotstd.query.adapters.ttbz import TTBZAdapter

        self.a = TTBZAdapter()

    def test_parse_real_row(self):
        rec = _fixture()["rows"][0]
        result = self.a._parse_result(rec, rec["standardNo"])
        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.standard_number, rec["standardNo"])
        self.assertEqual(result.standard_name, rec["standardTitleCn"])
        self.assertEqual(result.status, Status.ACTIVE.value)
        self.assertEqual(result.publish_date, rec["publishDate"])
        self.assertEqual(result.implementation_date, rec["implementDate"])
        self.assertEqual(result.responsible_dept, rec["organName"])
        self.assertEqual(result.hcno, rec["standardUniqueId"])
        self.assertEqual(result.match_status, "exact")
        # 接口无代替标准字段：留空，不臆造
        self.assertEqual(result.replaces, "")

    def test_abolish_date_mapped(self):
        rec = dict(_fixture()["rows"][0])
        rec["abolishDate"] = "2026-11-25"
        result = self.a._parse_result(rec, "")
        self.assertEqual(result.abolition_date, "2026-11-25")

    def test_withdrawn_status(self):
        rec = dict(_fixture()["rows"][0], standardStatusName=Status.WITHDRAWN.value)
        self.assertEqual(self.a._parse_result(rec, "").status, Status.WITHDRAWN.value)

    def test_unknown_status(self):
        rec = dict(_fixture()["rows"][0], standardStatusName="")
        self.assertEqual(self.a._parse_result(rec, "").status, Status.UNKNOWN.value)


class TestPagination(unittest.TestCase):
    """分页：首页无精确匹配时继续翻页，命中后停止。"""

    def setUp(self):
        from pilotstd.query.adapters.ttbz import TTBZAdapter

        self.a = TTBZAdapter()
        self.a._session_ready = True

    def test_second_page_when_no_exact_on_first(self):
        rows = _fixture()["rows"]
        self.a._fetch_page = MagicMock(
            side_effect=[
                (rows[1:2], 3),  # 首页：mismatch（T/BSCA 0002—2026）
                (rows[:1], 3),  # 第二页：命中 exact（T/BSCA 0006—2026）
            ]
        )
        results = self.a.query_standards("T/BSCA 0006—2026")
        self.assertEqual(self.a._fetch_page.call_count, 2)
        self.assertTrue(any(r.match_status == "exact" for r in results))

    def test_stops_after_exact_on_first_page(self):
        rows = _fixture()["rows"]
        self.a._fetch_page = MagicMock(return_value=(rows[:2], 10))
        self.a.query_standards("T/BSCA 0006—2026")
        self.assertEqual(self.a._fetch_page.call_count, 1)

    def test_stops_when_total_reached(self):
        rows = _fixture()["rows"]
        self.a._fetch_page = MagicMock(return_value=(rows[:2], 2))
        self.a.query_standards("T/XXXX")
        self.assertEqual(self.a._fetch_page.call_count, 1)

    def test_empty_first_page_returns_empty(self):
        self.a._fetch_page = MagicMock(return_value=([], 0))
        self.assertEqual(self.a.query_standards("T/NOPE"), [])

    def test_max_pages_cap(self):
        rows = _fixture()["rows"]
        self.a._fetch_page = MagicMock(return_value=(rows[:1], 999))
        self.a.query_standards("T/XXXX")
        self.assertEqual(self.a._fetch_page.call_count, TTBZAdapterMaxPages())


def TTBZAdapterMaxPages() -> int:
    from pilotstd.query.adapters.ttbz import TTBZAdapter

    return TTBZAdapter.MAX_PAGES


class TestSearchBest(unittest.TestCase):
    """`_search` 在多候选中优先选精确匹配。"""

    def setUp(self):
        from pilotstd.query.adapters.ttbz import TTBZAdapter

        self.a = TTBZAdapter()

    def test_picks_exact_match(self):
        rows = _fixture()["rows"]
        target = rows[0]["standardNo"]
        candidates = [self.a._parse_result(r, target) for r in rows[:3]]
        self.a.query_standards = MagicMock(return_value=candidates)
        best = self.a._search(target)
        self.assertIsNotNone(best)
        self.assertEqual(best.standard_number, target)


class TestNetworkErrors(unittest.TestCase):
    """网络/解析异常分支（`_fetch_page`）。"""

    def setUp(self):
        from pilotstd.query.adapters.ttbz import TTBZAdapter

        self.a = TTBZAdapter()
        self.a._session_ready = True

    def test_non_200(self):
        resp = MagicMock(status_code=500)
        with patch("pilotstd.query.adapters.ttbz.safe_post", return_value=resp):
            self.assertEqual(self.a._fetch_page({"pageNo": 1}), ([], 0))

    def test_none_response(self):
        with patch("pilotstd.query.adapters.ttbz.safe_post", return_value=None):
            self.assertEqual(self.a._fetch_page({"pageNo": 1}), ([], 0))

    def test_exception(self):
        with patch("pilotstd.query.adapters.ttbz.safe_post", side_effect=RuntimeError("boom")):
            self.assertEqual(self.a._fetch_page({"pageNo": 1}), ([], 0))

    def test_bad_json(self):
        resp = MagicMock(status_code=200)
        resp.json = MagicMock(side_effect=ValueError("not json"))
        with patch("pilotstd.query.adapters.ttbz.safe_post", return_value=resp):
            self.assertEqual(self.a._fetch_page({"pageNo": 1}), ([], 0))

    def test_missing_data_key(self):
        resp = MagicMock(status_code=200)
        resp.json = MagicMock(return_value={"result": True})
        with patch("pilotstd.query.adapters.ttbz.safe_post", return_value=resp):
            self.assertEqual(self.a._fetch_page({"pageNo": 1}), ([], 0))


if __name__ == "__main__":
    unittest.main()
