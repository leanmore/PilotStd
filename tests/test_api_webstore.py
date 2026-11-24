# tests/test_api_webstore.py
"""API Webstore 适配器单元测试（100% mock，网络层打桩）。

真实响应样本见 `tests/fixtures/api_webstore_sample.json`（2026-11-24 从 Coveo
`POST platform.cloud.coveo.com/rest/search/v2` 实测冻结，未人工构造）。
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pilotstd.core.status import Status
from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture() -> dict:
    return json.loads((FIXTURE_DIR / "api_webstore_sample.json").read_text(encoding="utf-8"))


class TestExtractProductcode(unittest.TestCase):
    """productcode 提取：覆盖实测的 7 种编号形态。"""

    def setUp(self):
        from pilotstd.query.adapters.api_webstore import ApiWebstoreAdapter

        self.a = ApiWebstoreAdapter()

    def test_numeric(self):
        self.assertEqual(self.a._extract_productcode("API STD 610-2026"), "610")
        self.assertEqual(self.a._extract_productcode("API 610"), "610")
        self.assertEqual(self.a._extract_productcode("610"), "610")

    def test_alphanumeric(self):
        self.assertEqual(self.a._extract_productcode("API SPEC 6D-2021"), "6D")
        self.assertEqual(self.a._extract_productcode("API SPEC 5CT"), "5CT")
        self.assertEqual(self.a._extract_productcode("API SPEC Q1-2023"), "Q1")

    def test_hyphenated(self):
        self.assertEqual(self.a._extract_productcode("API RP 2A-WSD"), "2A-WSD")
        self.assertEqual(self.a._extract_productcode("API TR 938-C"), "938-C")
        self.assertEqual(self.a._extract_productcode("API RP 579-1-2021"), "579-1")

    def test_joint_standard_takes_prefix(self):
        self.assertEqual(self.a._extract_productcode("API 579-1/ASME FFS-1"), "579-1")

    def test_unparseable_returns_empty(self):
        self.assertEqual(self.a._extract_productcode(""), "")
        self.assertEqual(self.a._extract_productcode("centrifugal pumps"), "")


class TestBuildBody(unittest.TestCase):
    def setUp(self):
        from pilotstd.query.adapters.api_webstore import ApiWebstoreAdapter

        self.a = ApiWebstoreAdapter()

    def test_exact_code_uses_aq(self):
        body = self.a._build_body("API STD 610-2026", 0, 10)
        self.assertEqual(body["aq"], '@productcode=="610" @producttype=="Standard"')
        self.assertEqual(body["q"], "")
        self.assertEqual(body["firstResult"], 0)
        self.assertEqual(body["numberOfResults"], 10)

    def test_free_text_falls_back_to_q(self):
        body = self.a._build_body("centrifugal pumps", 0, 10)
        self.assertEqual(body["q"], "centrifugal pumps")
        self.assertEqual(body["aq"], '@producttype=="Standard"')
        self.assertNotIn("productcode", body["aq"])


class TestParseResult(unittest.TestCase):
    """字段映射：基于真实 fixture。"""

    def setUp(self):
        from pilotstd.query.adapters.api_webstore import ApiWebstoreAdapter

        self.a = ApiWebstoreAdapter()

    @staticmethod
    def _rec(code: str) -> dict:
        for rec in _fixture()["rows"]:
            if rec["productcode"] == code:
                return {"raw": rec, "title": rec.get("_title") or rec.get("title")}
        raise AssertionError(f"fixture 缺 {code}")

    def test_parse_std_610(self):
        result = self.a._parse_result(self._rec("610"), "API STD 610-2026")
        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.standard_number, "API STD 610-2026")
        self.assertEqual(
            result.standard_name,
            "Centrifugal Pumps for Petroleum, Petrochemical and Natural Gas Industries",
        )
        self.assertEqual(result.status, Status.ACTIVE.value)
        self.assertEqual(result.publish_date, "2026-06-29")
        self.assertEqual(result.responsible_dept, "CRE: Committee on Refinery Equipment")
        self.assertEqual(result.hcno, "12c588567517c655fb336e10063670fa87338fb6ec97c66fdab2735ef2b2")
        self.assertEqual(result.source_site, "api_webstore")
        self.assertFalse(result.is_downloadable)

    def test_parse_spec_6d(self):
        result = self.a._parse_result(self._rec("6D"), "API SPEC 6D-2021")
        self.assertEqual(result.standard_number, "API SPEC 6D-2021")
        self.assertEqual(result.standard_name, "Specification for Valves")
        self.assertEqual(result.publish_date, "2021-11-01")

    def test_parse_spec_5ct(self):
        result = self.a._parse_result(self._rec("5CT"), "API SPEC 5CT")
        self.assertEqual(result.standard_number, "API SPEC 5CT-2023")
        self.assertEqual(result.standard_name, "Casing and Tubing")

    def test_match_status_exact_for_full_number(self):
        a = self.a._parse_result(self._rec("610"), "API STD 610-2026")
        self.assertEqual(a.match_status, "exact")

    def test_status_reaffirmed_maps_active(self):
        rec = {"raw": {"productcode": "682", "type": "STD", "status": "Reaffirmed", "title": "STD 682: X"}}
        self.assertEqual(self.a._parse_result(rec).status, Status.ACTIVE.value)

    def test_status_replaced_maps_superseded(self):
        rec = {"raw": {"productcode": "610", "type": "STD", "status": "Replaced", "title": "API STD 610: X"}}
        self.assertEqual(self.a._parse_result(rec).status, "被代替")

    def test_iso_date_conversion(self):
        from pilotstd.query.adapters.api_webstore import _iso_date

        self.assertEqual(_iso_date("06/29/2026"), "2026-06-29")
        self.assertEqual(_iso_date("2026-06-29"), "2026-06-29")
        self.assertEqual(_iso_date(""), "")
        self.assertEqual(_iso_date("bad"), "bad")


class TestSearchCandidates(unittest.TestCase):
    """检索与网络异常分支（safe_post 打桩）。"""

    def setUp(self):
        from pilotstd.query.adapters.api_webstore import ApiWebstoreAdapter

        self.a = ApiWebstoreAdapter()

    def _resp(self, payload, status=200):
        resp = MagicMock()
        resp.status_code = status
        resp.json = MagicMock(return_value=payload)
        return resp

    def test_search_returns_candidates(self):
        payload = {"totalCount": 3, "results": [{"raw": r, "title": r.get("title")} for r in _fixture()["rows"]]}
        with patch("pilotstd.query.network.safe_post", return_value=self._resp(payload)):
            results = self.a._search_candidates("API STD 610-2026")
        self.assertEqual(len(results), 3)
        self.assertTrue(all(isinstance(r, QueryResult) for r in results))

    def test_search_empty_results(self):
        with patch("pilotstd.query.network.safe_post", return_value=self._resp({"totalCount": 0, "results": []})):
            self.assertEqual(self.a._search_candidates("API STD 610"), [])

    def test_search_non_200(self):
        with patch("pilotstd.query.network.safe_post", return_value=self._resp(None, status=500)):
            self.assertEqual(self.a._search_candidates("API STD 610"), [])

    def test_search_network_none(self):
        with patch("pilotstd.query.network.safe_post", return_value=None):
            self.assertEqual(self.a._search_candidates("API STD 610"), [])

    def test_search_bad_json(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(side_effect=ValueError("not json"))
        with patch("pilotstd.query.network.safe_post", return_value=resp):
            self.assertEqual(self.a._search_candidates("API STD 610"), [])

    def test_401_then_refresh_retries(self):
        payload = {"totalCount": 1, "results": [{"raw": _fixture()["rows"][0]}]}
        calls = [self._resp(None, status=401), self._resp(payload)]

        def fake_post(*args, **kwargs):
            return calls.pop(0)

        with patch("pilotstd.query.network.safe_post", side_effect=fake_post), patch.object(
            self.a, "_refresh_token", return_value=True
        ):
            results = self.a._search_candidates("API STD 610")
        self.assertEqual(len(results), 1)


class TestRefreshToken(unittest.TestCase):
    """token 自愈：从公开 bundle 重新解析 UUID。"""

    def setUp(self):
        from pilotstd.query.adapters.api_webstore import ApiWebstoreAdapter

        self.a = ApiWebstoreAdapter()

    def test_refresh_finds_token_in_bundle(self):
        page = MagicMock(text='<script src="/dist/webstore/static/js/main.abc123.js"></script>')
        bundle = MagicMock(text='...Bearer " + "11111111-2222-3333-4444-555555555555"}...')
        self.a._session.get = MagicMock(side_effect=[page, bundle])
        self.assertTrue(self.a._refresh_token())
        self.assertEqual(self.a._token, "11111111-2222-3333-4444-555555555555")

    def test_refresh_no_bundle_returns_false(self):
        page = MagicMock(text="<html>no script</html>")
        self.a._session.get = MagicMock(return_value=page)
        self.assertFalse(self.a._refresh_token())

    def test_refresh_same_token_returns_false(self):
        page = MagicMock(text='src="main.abc.js"')
        bundle = MagicMock(text=f"Bearer {self.a.TOKEN}")
        self.a._session.get = MagicMock(side_effect=[page, bundle])
        self.assertFalse(self.a._refresh_token())


if __name__ == "__main__":
    unittest.main()
