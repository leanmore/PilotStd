# tests/test_cqis.py
"""重庆标准信息平台适配器单元测试（100% mock，网络层打桩）。

真实响应样本见 `tests/fixtures/cqis_sample.json`（2026-11-24 从
`POST http://db.cqis.cn/LocalStandard/GetDB50ShareList` 实测冻结，未人工构造）。
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pilotstd.core.status import Status
from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture() -> dict:
    return json.loads((FIXTURE_DIR / "cqis_sample.json").read_text(encoding="utf-8"))


class TestCqisParseResult(unittest.TestCase):
    """字段映射：全部基于真实 fixture。"""

    def setUp(self):
        from pilotstd.query.adapters.cqis import CqisAdapter

        self.a = CqisAdapter()

    def test_parse_result_from_fixture(self):
        rec = _fixture()["rows"][0]
        result = self.a._parse_result(rec, "DB50/T 950-2026")
        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.standard_number, "DB50/T 950-2026")
        self.assertEqual(result.standard_name, "荣昌卤鹅加工技术规范")
        # 真实样本：ReleaseStatus=现行，但实施日期 2026-12-01 晚于冻结日 2026-11-24
        # → 按 dbba 同口径修正为「即将实施」（不是「现行」）。
        self.assertEqual(result.status, Status.UPCOMING.value)
        self.assertEqual(result.publish_date, "2026-09-24")
        self.assertEqual(result.implementation_date, "2026-12-01")
        self.assertEqual(result.replaces, "DB50/T 950-2019")
        self.assertEqual(result.hcno, "dba6c814-91c0-483d-a691-2f08a3029833")
        self.assertEqual(result.responsible_dept, "重庆市市场监督管理局")
        self.assertEqual(result.source_site, "cqis")
        self.assertFalse(result.is_downloadable)

    def test_parse_result_withdrawn(self):
        """废止状态正确映射（fixture 第 2 条）。"""
        rec = _fixture()["rows"][1]
        result = self.a._parse_result(rec, "DB50/T 950-2019")
        self.assertEqual(result.standard_number, "DB50/T 950-2019")
        self.assertEqual(result.status, Status.WITHDRAWN.value)
        self.assertEqual(result.publish_date, "2019-12-02")

    def test_parse_result_upcoming_when_implement_date_future(self):
        """现行 + 实施日期在未来 → 即将实施（与 dbba 同口径）。"""
        rec = {
            "Project_FinishCODE": "DB50/T 9999-2099",
            "BZName": "未来标准",
            "ReleaseStatus": "现行",
            "ReleaseTime": "2099-01-01 00:00:00",
            "ActiveTime": "2099-06-01 00:00:00",
        }
        result = self.a._parse_result(rec, "")
        self.assertEqual(result.status, Status.UPCOMING.value)

    def test_parse_result_partial_fields(self):
        """缺失字段不抛异常，空值兜底。"""
        result = self.a._parse_result({"Project_FinishCODE": "DB50/T 1-2020"}, "")
        self.assertEqual(result.standard_number, "DB50/T 1-2020")
        self.assertEqual(result.standard_name, "")
        self.assertEqual(result.publish_date, "")
        self.assertEqual(result.replaces, "")

    def test_parse_result_empty(self):
        result = self.a._parse_result({}, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "")

    def test_parse_result_match_status(self):
        """与搜索目标同一编号时应为 exact（此前 ASME 拆号类缺陷的回归点）。"""
        rec = _fixture()["rows"][0]
        result = self.a._parse_result(rec, "DB50/T 950-2026")
        self.assertEqual(result.match_status, "exact")


class TestCqisSearch(unittest.TestCase):
    """检索请求构造与网络异常分支（safe_post 打桩）。"""

    def setUp(self):
        from pilotstd.query.adapters.cqis import CqisAdapter

        self.a = CqisAdapter()

    def test_build_search_data_uses_finish_code(self):
        """标准号过滤必须走 `queryJson.FinishCode`（BZName 匹配的是名称）。"""
        data = self.a._build_search_data("DB50/T 950")
        self.assertEqual(data["page"], "1")
        self.assertIn("queryJson", data)
        q = json.loads(data["queryJson"])
        self.assertEqual(q["FinishCode"], "DB50/T 950")
        self.assertEqual(q["BZName"], "")

    def _mock_post(self, payload=None, status=200, exc=None):
        resp = MagicMock()
        resp.status_code = status
        resp.json = MagicMock(return_value=payload)
        return patch(
            "pilotstd.query.network.safe_post",
            side_effect=exc if exc else None,
            return_value=None if exc else resp,
        )

    def test_search_candidates_from_fixture(self):
        with self._mock_post(_fixture()):
            results = self.a._search_candidates("DB50/T 950")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(r, QueryResult) for r in results))
        self.assertEqual(results[0].standard_number, "DB50/T 950-2026")

    def test_search_candidates_empty_rows(self):
        with self._mock_post({"rows": [], "total": 0}):
            self.assertEqual(self.a._search_candidates("DB50/T 0"), [])

    def test_search_candidates_non_200(self):
        with self._mock_post(None, status=500):
            self.assertEqual(self.a._search_candidates("DB50/T 950"), [])

    def test_search_candidates_bad_json(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(side_effect=ValueError("not json"))
        with patch("pilotstd.query.network.safe_post", return_value=resp):
            self.assertEqual(self.a._search_candidates("DB50/T 950"), [])

    def test_search_candidates_network_exception(self):
        with patch("pilotstd.query.network.safe_post", side_effect=RuntimeError("timeout")):
            self.assertEqual(self.a._search_candidates("DB50/T 950"), [])


if __name__ == "__main__":
    unittest.main()
