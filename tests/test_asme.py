# tests/test_asme.py
"""ASME 适配器单元测试（100% mock，网络层打桩）。

真实响应样本见 `tests/fixtures/asme_sample.json`（2026-11-24 从
`GET https://www.asme.org/api/products?fullDesignator=…` 实测冻结，未人工构造）。
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pilotstd.core.status import Status
from pilotstd.query.models import QueryResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture() -> dict:
    return json.loads((FIXTURE_DIR / "asme_sample.json").read_text(encoding="utf-8"))


def _row(designator: str) -> dict:
    for rec in _fixture()["rows"]:
        if rec.get("FullDesignator") == designator:
            return rec
    raise AssertionError(f"fixture 缺 {designator}")


class TestNormalizeDesignator(unittest.TestCase):
    """designator 归一化：覆盖实测可命中的形态。"""

    def setUp(self):
        from pilotstd.query.adapters.asme import AsmeAdapter

        self.a = AsmeAdapter()

    def test_b_series(self):
        self.assertEqual(self.a._normalize_designator("ASME B16.5-2025"), "B16.5")
        self.assertEqual(self.a._normalize_designator("ASME B31.3-2024"), "B31.3")
        self.assertEqual(self.a._normalize_designator("B16.5"), "B16.5")

    def test_bpvc_dotted(self):
        self.assertEqual(self.a._normalize_designator("ASME BPVC.VIII.1-2025"), "BPVC.VIII.1")
        self.assertEqual(self.a._normalize_designator("ASME BPVC.IX-2021"), "BPVC.IX")

    def test_bpvc_section_text(self):
        """`Section VIII Div.1` → `BPVC.VIII.1`（P1-7.1 报告的 ASME 卷册篇形态）。"""
        self.assertEqual(
            self.a._normalize_designator("ASME BPVC Section VIII Div.1-2021"), "BPVC.VIII.1"
        )
        self.assertEqual(self.a._normalize_designator("BPVC Section VIII Division 1"), "BPVC.VIII.1")

    def test_bpvc_section_part(self):
        self.assertEqual(self.a._normalize_designator("ASME BPVC Section II Part D"), "BPVC.II.D")

    def test_ptc_and_y14(self):
        self.assertEqual(self.a._normalize_designator("ASME PTC 4-2013"), "PTC 4")
        self.assertEqual(self.a._normalize_designator("ASME Y14.5-2018"), "Y14.5")
        self.assertEqual(self.a._normalize_designator("ASME CSD-1-2024"), "CSD-1")

    def test_joint_designator_kept(self):
        self.assertEqual(
            self.a._normalize_designator("ASME A112.18.1/CSA B125.1"), "A112.18.1/CSA B125.1"
        )

    def test_empty(self):
        self.assertEqual(self.a._normalize_designator(""), "")
        self.assertEqual(self.a._normalize_designator("ASME"), "")


class TestParseResult(unittest.TestCase):
    """字段映射：基于真实 fixture。"""

    def setUp(self):
        from pilotstd.query.adapters.asme import AsmeAdapter

        self.a = AsmeAdapter()

    def test_parse_b16_5(self):
        result = self.a._parse_result(_row("B16.5"), "ASME B16.5-2025")
        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.standard_number, "ASME B16.5-2025")
        self.assertEqual(
            result.standard_name,
            "Pipe Flanges and Flanged Fittings: NPS 1/2 through NPS 24, Metric/Inch Standard",
        )
        self.assertEqual(result.status, Status.ACTIVE.value)
        self.assertEqual(result.publish_date, "2025")
        self.assertEqual(result.hcno, "M01525")
        self.assertEqual(result.source_site, "asme")
        self.assertFalse(result.is_downloadable)
        self.assertEqual(result.match_status, "exact")

    def test_parse_bpvc(self):
        result = self.a._parse_result(_row("BPVC.VIII.1"), "ASME BPVC Section VIII Div.1-2025")
        self.assertEqual(result.standard_number, "ASME BPVC.VIII.1-2025")
        self.assertIn("Pressure Vessels", result.standard_name)

    def test_parse_ptc(self):
        result = self.a._parse_result(_row("PTC 4"), "ASME PTC 4-2013")
        self.assertEqual(result.standard_number, "ASME PTC 4-2013")
        self.assertEqual(result.standard_name, "Fired Steam Generators")
        self.assertEqual(result.publish_date, "2013")

    def test_old_request_year_marks_superseded(self):
        """目录只索引最新版：请求更旧年份 → 该版已被代替。"""
        result = self.a._parse_result(_row("B16.5"), "ASME B16.5-2020")
        self.assertEqual(result.status, Status.SUPERSEDED.value)
        self.assertEqual(result.match_status, "newer")

    def test_no_year_request_is_active(self):
        result = self.a._parse_result(_row("B16.5"), "ASME B16.5")
        self.assertEqual(result.status, Status.ACTIVE.value)

    def test_partial_fields(self):
        result = self.a._parse_result({"FullDesignator": "X1.1"})
        self.assertEqual(result.standard_number, "ASME X1.1")
        self.assertEqual(result.publish_date, "")


class TestSearchCandidates(unittest.TestCase):
    """检索与网络异常分支（`_session.get` 打桩）。"""

    def setUp(self):
        from pilotstd.query.adapters.asme import AsmeAdapter

        self.a = AsmeAdapter()

    def _resp(self, payload, status=200):
        resp = MagicMock()
        resp.status_code = status
        resp.json = MagicMock(return_value=payload)
        return resp

    def test_search_returns_candidates(self):
        payload = {"total": 1, "results": [_row("B16.5")]}
        self.a._session.get = MagicMock(return_value=self._resp(payload))
        results = self.a._search_candidates("ASME B16.5-2025")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], QueryResult)

    def test_search_passes_normalized_designator(self):
        payload = {"total": 1, "results": [_row("BPVC.VIII.1")]}
        self.a._session.get = MagicMock(return_value=self._resp(payload))
        self.a._search_candidates("ASME BPVC Section VIII Div.1-2021")
        _, kwargs = self.a._session.get.call_args
        self.assertEqual(kwargs["params"]["fullDesignator"], "BPVC.VIII.1")

    def test_search_empty(self):
        self.a._session.get = MagicMock(return_value=self._resp({"total": 0, "results": []}))
        self.assertEqual(self.a._search_candidates("ASME ZZZ99.9"), [])

    def test_search_non_200(self):
        self.a._session.get = MagicMock(return_value=self._resp(None, status=500))
        self.assertEqual(self.a._search_candidates("ASME B16.5"), [])

    def test_search_network_exception(self):
        self.a._session.get = MagicMock(side_effect=RuntimeError("timeout"))
        self.assertEqual(self.a._search_candidates("ASME B16.5"), [])

    def test_search_bad_json(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(side_effect=ValueError("not json"))
        self.a._session.get = MagicMock(return_value=resp)
        self.assertEqual(self.a._search_candidates("ASME B16.5"), [])

    def test_bpvc_part_d_falls_back_to_c_or_m(self):
        """`BPVC.II.D` 在目录中细分为 `.C`/`.M`：精确查空时补查。"""
        empty = self._resp({"total": 0, "results": []})
        hit = self._resp({"total": 1, "results": [_row("BPVC.VIII.1")]})
        self.a._session.get = MagicMock(side_effect=[empty, hit])
        results = self.a._search_candidates("ASME BPVC Section II Part D")
        self.assertEqual(len(results), 1)
        called = [c[1]["params"]["fullDesignator"] for c in self.a._session.get.call_args_list]
        self.assertEqual(called, ["BPVC.II.D", "BPVC.II.D.C"])


if __name__ == "__main__":
    unittest.main()
