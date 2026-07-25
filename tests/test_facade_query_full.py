# tests/test_facade_query_full.py
"""QueryHandler 单元测试 — 覆盖 _query.py 全部公开方法和核心私有方法。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.manager.facade._query import QueryHandler
from pilotstd.query.models import BatchQueryStats, QueryResult


def _make_parsed_item(
    logical_code: str = "GB",
    number: str = "19001",
    year: str = "2016",
    std_name: str = "质量管理体系",
    part: str = "",
    num_prefix: str = "T",
    num_suffix: str = "",
    source_path: str = "/fake/path.pdf",
) -> MagicMock:
    """构造一条 mock 解析条目，各属性可覆盖。"""
    p = MagicMock()
    p.logical_code = logical_code
    p.number = number
    p.year = year
    p.std_name = std_name
    p.part = part
    p.num_prefix = num_prefix
    p.num_suffix = num_suffix
    p.source_path = source_path
    return p


class TestQueryHandler(unittest.TestCase):
    """QueryHandler 全部方法测试。"""

    def setUp(self):
        # 构造 ManagerCore mock
        self.core = MagicMock()
        self.core.cfg = MagicMock()
        self.core.cfg.get.return_value = ""
        self.core.query_engine = MagicMock()
        self.core.classifier = MagicMock()
        self.core.pending_svc = MagicMock()
        self.core.pending_list = []
        self.core.notification_mgr = MagicMock()
        self.core.download_list = []
        self.core.expire_list = []
        self.core.query_results = []
        self.core.parsed_results = []
        self.core.queried_items: list[MagicMock] = []
        self.core.scheduled_svc = MagicMock()

        self.handler = QueryHandler(self.core)

    # ── __init__ ──

    def test_init_stores_core(self):
        self.assertIs(self.handler._core, self.core)

    def test_cat_label_keys(self):
        expected = {"gb", "industry", "db", "iso_iec", "foreign", "group", "enterprise"}
        self.assertEqual(set(self.handler._CAT_LABEL.keys()), expected)

    # ── _build_result_from_cache ──

    def test_build_result_from_cache_basic(self):
        data = {
            "standard_name": "测试标准",
            "status": "现行",
            "replaces": "GB/T 19001-2008",
            "implementation_date": "2017-07-01",
            "responsible_dept": "SAC",
            "publish_date": "2016-12-30",
            "abolition_date": "",
            "hcno": "abc123",
            "is_downloadable": True,
        }
        r = self.handler._build_result_from_cache("GB/T 19001-2016", data)
        self.assertIsInstance(r, QueryResult)
        self.assertEqual(r.standard_number, "GB/T 19001-2016")
        self.assertEqual(r.standard_name, "测试标准")
        self.assertEqual(r.status, "现行")
        self.assertEqual(r.replaces, "GB/T 19001-2008")
        self.assertEqual(r.source_site, "web_announcement_match")
        self.assertEqual(r.source, "web端公告缓存")
        self.assertEqual(r.match_status, "exact")
        self.assertTrue(r.is_downloadable)

    def test_build_result_from_cache_fallback_fields(self):
        """data 中使用 std_name / effect_status / replaces_code 别名。"""
        data = {"std_name": "别名测试", "effect_status": "废止", "replaces_code": "GB/T 1.1-2009"}
        r = self.handler._build_result_from_cache("GB/T 1.1-2020", data)
        self.assertEqual(r.standard_name, "别名测试")
        self.assertEqual(r.status, "废止")
        self.assertEqual(r.replaces, "GB/T 1.1-2009")

    def test_build_result_from_cache_is_adopted(self):
        data = {"standard_name": "采标标准", "is_adopted": True}
        r = self.handler._build_result_from_cache("GB/T 1-2020", data)
        self.assertTrue(r.is_adopted)

    def test_build_result_from_cache_empty_data(self):
        r = self.handler._build_result_from_cache("GB/T 1-2020", {})
        self.assertEqual(r.standard_name, "")
        self.assertEqual(r.status, "")

    def test_build_result_from_cache_none_data(self):
        r = self.handler._build_result_from_cache("GB/T 1-2020", None)  # type: ignore[arg-type]
        self.assertEqual(r.standard_name, "")

    # ── _query_announcement_match ──

    @patch("pilotstd.manager.facade._query_exec.requests.get")
    def test_announcement_match_disabled_no_api_key(self, mock_get):
        self.core.cfg.get.side_effect = lambda key, default=None: {
            "query.announcement_url": "http://localhost:9028",
            "network.timeout": 30,
            "query.announcement_api_key": "",
        }.get(key, default)
        result = self.handler._query_announcement_match("GB/T 1-2020")
        self.assertIsNone(result)
        mock_get.assert_not_called()

    @patch("pilotstd.manager.facade._query_exec.requests.get")
    def test_announcement_match_found(self, mock_get):
        self.core.cfg.get.side_effect = lambda key, default=None: {
            "query.announcement_url": "http://localhost:9028",
            "network.timeout": 30,
            "query.announcement_api_key": "test-key",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"found": True, "data": {"standard_name": "测试"}, "cached_at": "2025-01-01"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = self.handler._query_announcement_match("GB/T 1-2020")
        self.assertIsNotNone(result)
        self.assertTrue(result["data"]["standard_name"] == "测试")

    @patch("pilotstd.manager.facade._query_exec.requests.get")
    def test_announcement_match_not_found(self, mock_get):
        self.core.cfg.get.side_effect = lambda key, default=None: {
            "query.announcement_url": "http://localhost:9028",
            "network.timeout": 30,
            "query.announcement_api_key": "test-key",
        }.get(key, default)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"found": False}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = self.handler._query_announcement_match("GB/T 1-2020")
        self.assertIsNone(result)

    @patch("pilotstd.manager.facade._query_exec.requests.get")
    def test_announcement_match_timeout(self, mock_get):
        import requests as rq

        self.core.cfg.get.side_effect = lambda key, default=None: {
            "query.announcement_url": "http://localhost:9028",
            "network.timeout": 30,
            "query.announcement_api_key": "test-key",
        }.get(key, default)
        mock_get.side_effect = rq.exceptions.Timeout()
        result = self.handler._query_announcement_match("GB/T 1-2020")
        self.assertIsNone(result)

    @patch("pilotstd.manager.facade._query_exec.requests.get")
    def test_announcement_match_connection_error(self, mock_get):
        import requests as rq

        self.core.cfg.get.side_effect = lambda key, default=None: {
            "query.announcement_url": "http://localhost:9028",
            "network.timeout": 30,
            "query.announcement_api_key": "test-key",
        }.get(key, default)
        mock_get.side_effect = rq.exceptions.ConnectionError("refused")
        result = self.handler._query_announcement_match("GB/T 1-2020")
        self.assertIsNone(result)

    # ── _query_via_engine ──

    def test_query_via_engine_calls_query_standards(self):
        items = [_make_parsed_item(), _make_parsed_item(number="1", std_name="另一个")]
        mock_result = [QueryResult(standard_number="a", standard_name="x")]
        self.core.query_engine.query_standards.return_value = mock_result

        results = self.handler._query_via_engine(items, None)
        self.core.query_engine.query_standards.assert_called_once()
        call_args = self.core.query_engine.query_standards.call_args
        parsed_tuples = call_args[0][0]
        self.assertEqual(len(parsed_tuples), 2)
        self.assertEqual(parsed_tuples[0][0], "GB")
        self.assertEqual(results, mock_result)

    def test_query_via_engine_with_site_and_force_refresh(self):
        items = [_make_parsed_item()]
        self.core.query_engine.query_standards.return_value = []
        self.handler._query_via_engine(items, None, site="std_gov", force_refresh=True)
        call_kwargs = self.core.query_engine.query_standards.call_args[1]
        self.assertEqual(call_kwargs["preferred_site"], "std_gov")
        self.assertTrue(call_kwargs["force_refresh"])

    # ── _query_via_cache ──

    @patch.object(QueryHandler, "_query_announcement_match")
    def test_query_via_cache_all_hit(self, mock_match):
        mock_match.return_value = {"data": {"standard_name": "cached", "status": "现行"}}
        items = [_make_parsed_item(), _make_parsed_item(number="1")]
        self.core.query_engine.query_standards.return_value = []

        results = self.handler._query_via_cache(items, None)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].standard_name, "cached")
        self.assertEqual(results[1].standard_name, "cached")
        self.core.query_engine.query_standards.assert_not_called()

    @patch.object(QueryHandler, "_query_announcement_match")
    def test_query_via_cache_partial_hit(self, mock_match):
        """第一条命中缓存，第二条未命中→降级到实时引擎。"""
        mock_match.side_effect = [
            {"data": {"standard_name": "cached"}},  # 命中
            None,  # 未命中
        ]
        items = [_make_parsed_item(), _make_parsed_item(number="1")]
        live_result = QueryResult(standard_number="GB 1-2020", standard_name="live")
        self.core.query_engine.query_standards.return_value = [live_result]

        results = self.handler._query_via_cache(items, None)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].standard_name, "cached")
        self.assertEqual(results[1].standard_name, "live")
        self.assertEqual(results[1].source, "live_fallback")
        self.core.query_engine.query_standards.assert_called_once()

    @patch.object(QueryHandler, "_query_announcement_match")
    def test_query_via_cache_with_result_callback(self, mock_match):
        mock_match.return_value = {"data": {"standard_name": "cached"}}
        items = [_make_parsed_item(), _make_parsed_item(number="1")]
        mock_cb = MagicMock()
        self.core.query_engine.query_standards.return_value = []

        self.handler._query_via_cache(items, mock_cb)
        # 回调应被调用 2 次（全部命中）
        self.assertEqual(mock_cb.call_count, 2)

    # ── _finalize_query ──

    def test_finalize_query_basic(self):
        items = [_make_parsed_item(), _make_parsed_item(number="1")]
        results = [
            QueryResult(standard_number="a", standard_name="found", match_status="exact", is_downloadable=True),
            QueryResult(standard_number="b", standard_name="", error_message="not found"),
        ]
        self.core.pending_list = []

        res, stats = self.handler._finalize_query(items, results)
        self.assertEqual(len(res), 2)
        self.assertIsInstance(stats, BatchQueryStats)
        self.assertEqual(stats.total, 2)
        self.assertEqual(stats.found, 1)
        self.assertEqual(stats.exact, 1)
        self.assertEqual(stats.downloadable, 2)  # is_downloadable 默认为 True
        # query_results 应被写入
        self.assertEqual(self.core.query_results, results)

    def test_finalize_query_with_pending(self):
        items = [_make_parsed_item()]
        results = [QueryResult(standard_number="a", standard_name="found", match_status="mismatch")]
        self.core.pending_list = [items[0]]

        self.handler._finalize_query(items, results)
        self.core.pending_svc.record_pending.assert_called_once_with([items[0]])
        self.core.notification_mgr.send_event.assert_called()

    def test_finalize_query_notification_disabled(self):
        items = [_make_parsed_item()]
        results = [QueryResult(standard_number="a", standard_name="found")]
        self.core.notification_mgr = None
        self.core.pending_list = []

        res, stats = self.handler._finalize_query(items, results)
        self.assertIsNotNone(stats)

    # ── query ──

    def test_query_uses_cache_when_no_site(self):
        self.core.cfg.get.return_value = True  # use_announcement_match = True
        items = [_make_parsed_item()]
        self.core.parsed_results = items

        # mock _query_via_cache
        with patch.object(self.handler, "_query_via_cache") as mock_via_cache:
            mock_via_cache.return_value = [QueryResult(standard_number="x", standard_name="y")]
            # mock _finalize_query
            with patch.object(self.handler, "_finalize_query") as mock_finalize:
                mock_finalize.return_value = ([], BatchQueryStats())
                self.handler.query(parsed_list=items)

            mock_via_cache.assert_called_once()

    def test_query_uses_engine_with_site(self):
        items = [_make_parsed_item()]
        self.core.parsed_results = items

        with patch.object(self.handler, "_query_via_engine") as mock_via_engine:
            mock_via_engine.return_value = [QueryResult(standard_number="x", standard_name="y")]
            with patch.object(self.handler, "_finalize_query") as mock_finalize:
                mock_finalize.return_value = ([], BatchQueryStats())
                self.handler.query(parsed_list=items, site="std_gov")

            mock_via_engine.assert_called_once()

    def test_query_with_progress_callback(self):
        items = [_make_parsed_item(), _make_parsed_item(number="1")]
        self.core.parsed_results = items
        self.core.cfg.get.return_value = False  # 不使用公告缓存

        progress_cb = MagicMock()
        with patch.object(self.handler, "_query_via_engine") as mock_eng:
            mock_eng.return_value = [QueryResult(standard_number="x", standard_name="y")] * 2
            with patch.object(self.handler, "_finalize_query") as mock_fin:
                mock_fin.return_value = ([], BatchQueryStats())
                self.handler.query(parsed_list=items, progress_callback=progress_cb)

            # progress_callback 应被透传，engine_progress 被调用
            call_kwargs = mock_eng.call_args[1]
            self.assertIsNotNone(call_kwargs.get("progress_callback"))

    # ── query_stream ──

    def test_query_stream_delegates_to_query(self):
        items = [_make_parsed_item()]
        with patch.object(self.handler, "query") as mock_query:
            mock_query.return_value = ([], BatchQueryStats())
            self.handler.query_stream(items, on_progress=lambda c, t: None, on_result=lambda i, r: None)
            mock_query.assert_called_once_with(
                parsed_list=items,
                force_refresh=False,
                progress_callback=mock_query.call_args[1]["progress_callback"],
                result_callback=mock_query.call_args[1]["result_callback"],
                site=None,
            )

    # ── _report_category_breakdown ──

    def test_report_category_breakdown(self):
        items = [
            _make_parsed_item(logical_code="GB", number="19001"),
            _make_parsed_item(logical_code="HB", number="1"),
        ]
        results = [
            QueryResult(standard_number="GB", standard_name="国标"),
            QueryResult(standard_number="HB", standard_name=""),
        ]
        self.handler._report_category_breakdown(items, results)
        # 不抛异常即通过；日志已由框架输出

    def test_report_category_breakdown_with_pending(self):
        items = [_make_parsed_item()]
        results = [QueryResult(standard_number="GB", standard_name="x", match_status="mismatch")]
        self.core.pending_list = [items[0]]
        self.handler._report_category_breakdown(items, results)
        # 不抛异常即通过

    # ── _report_download_queue ──

    def test_report_download_queue(self):
        items = [_make_parsed_item()]
        results = [QueryResult(standard_number="GB", standard_name="x")]
        self.handler._report_download_queue(items, results)

    # ── _report_query_summary ──

    def test_report_query_summary(self):
        items = [_make_parsed_item(), _make_parsed_item(number="1")]
        results = [
            QueryResult(standard_number="a", standard_name="found", source_site="std_gov", match_status="exact"),
            QueryResult(standard_number="b", standard_name="", match_status="older"),
        ]
        stats = BatchQueryStats(total=2, found=1, exact=1)
        self.core.pending_list = []
        self.handler._report_query_summary(stats, items, results)

    # ── _classify_after_query ──

    def test_classify_after_query(self):
        items = [_make_parsed_item()]
        results = [QueryResult(standard_number="a", standard_name="x")]
        self.handler._classify_after_query(items, results)
        self.core.classifier.classify.assert_called_once_with(
            results,
            items,
            self.core.download_list,
            self.core.expire_list,
            self.core.pending_list,
            notification_mgr=self.core.notification_mgr,
        )

    # ── _resolve_replaces ──

    def test_resolve_replaces(self):
        self.core.classifier.resolve_replaces.return_value = "GB/T 19001-2008"
        result = self.handler._resolve_replaces("GB/T 19001-2016")
        self.assertEqual(result, "GB/T 19001-2008")
        self.core.classifier.resolve_replaces.assert_called_once_with("GB/T 19001-2016")

    # ── get_quota_info ──

    def test_get_quota_info(self):
        self.core.query_engine.get_quota_info.return_value = {"std_gov": 100}
        result = self.handler.get_quota_info()
        self.assertEqual(result, {"std_gov": 100})

    # ── plan_batch ──

    def test_plan_batch(self):
        self.core.query_engine.plan_batch.return_value = [("std_gov", 50)]
        result = self.handler.plan_batch(50)
        self.assertEqual(result, [("std_gov", 50)])
        self.core.query_engine.plan_batch.assert_called_once_with(50)

    # ── get_stage_queue ──

    def test_get_stage_queue_download(self):
        item = _make_parsed_item()
        self.core.download_list = [item]
        result = self.handler.get_stage_queue("download")
        self.assertEqual(result, [item])

    def test_get_stage_queue_expire(self):
        item = _make_parsed_item()
        self.core.expire_list = [item]
        result = self.handler.get_stage_queue("expire")
        self.assertEqual(result, [item])

    def test_get_stage_queue_pending(self):
        item = _make_parsed_item()
        self.core.pending_list = [item]
        result = self.handler.get_stage_queue("pending")
        self.assertEqual(result, [item])

    def test_get_stage_queue_queried(self):
        item = _make_parsed_item()
        self.core.queried_items = [item]
        result = self.handler.get_stage_queue("queried")
        self.assertEqual(result, [item])

    def test_get_stage_queue_parsed_fallback(self):
        item = _make_parsed_item()
        self.core.parsed_results = [item]
        self.core.queried_items = []
        result = self.handler.get_stage_queue("unknown")
        self.assertEqual(result, [item])

    # ── get_stage_summary ──

    def test_get_stage_summary(self):
        self.core.download_list = [_make_parsed_item(), _make_parsed_item()]
        self.core.expire_list = [_make_parsed_item()]
        self.core.pending_list = []
        self.core.queried_items = [_make_parsed_item()]

        summary = self.handler.get_stage_summary()
        self.assertEqual(summary["download"], 2)
        self.assertEqual(summary["expire"], 1)
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(summary["total"], 1)

    # ── record_pending ──

    def test_record_pending(self):
        items = [_make_parsed_item()]
        self.handler.record_pending(items)
        self.core.pending_svc.record_pending.assert_called_once_with(items)

    # ── resolve_pending ──

    def test_resolve_pending(self):
        items = [{"standard_number": "GB/T 1-2020"}]
        self.handler.resolve_pending(items, "download")
        self.core.pending_svc.resolve_pending.assert_called_once_with(items, "download")

    # ── get_pending_items ──

    def test_get_pending_items(self):
        self.core.pending_svc.get_pending_items.return_value = [{"standard_number": "GB"}]
        result = self.handler.get_pending_items()
        self.assertEqual(result, [{"standard_number": "GB"}])

    # ── increment_requery_count ──

    def test_increment_requery_count(self):
        self.core.pending_svc.increment_requery_count.return_value = 3
        result = self.handler.increment_requery_count("GB/T 1")
        self.assertEqual(result, 3)

    # ── is_requery_exhausted ──

    def test_is_requery_exhausted(self):
        self.core.pending_svc.is_requery_exhausted.return_value = True
        self.assertTrue(self.handler.is_requery_exhausted("GB/T 1"))

    # ── mark_manual_required ──

    def test_mark_manual_required(self):
        self.handler.mark_manual_required("GB/T 1")
        self.core.pending_svc.mark_manual_required.assert_called_once_with("GB/T 1")

    # ── get_requery_count ──

    def test_get_requery_count(self):
        self.core.pending_svc.get_requery_count.return_value = 2
        self.assertEqual(self.handler.get_requery_count("GB/T 1"), 2)

    # ── query_local_cache ──

    def test_query_local_cache(self):
        items = [_make_parsed_item()]
        self.core.pending_svc.query_local_cache.return_value = [{"result": "x"}]
        result = self.handler.query_local_cache(items)
        self.assertEqual(result, [{"result": "x"}])

    # ── query_by_numbers ──

    def test_query_by_numbers(self):
        self.core.scheduled_svc.query_by_numbers.return_value = ([], BatchQueryStats())
        nums = ["GB/T 19001-2016"]
        results, stats = self.handler.query_by_numbers(nums)
        self.core.scheduled_svc.query_by_numbers.assert_called_once_with(nums, False, None)
        self.assertIsInstance(stats, BatchQueryStats)

    def test_query_by_numbers_with_opts(self):
        self.core.scheduled_svc.query_by_numbers.return_value = ([], BatchQueryStats())
        self.handler.query_by_numbers(["GB/T 1"], force_refresh=True, preferred_site="std_gov")
        self.core.scheduled_svc.query_by_numbers.assert_called_once_with(["GB/T 1"], True, "std_gov")

    # ── get_query_sites ──

    def test_get_query_sites(self):
        self.core.query_engine.get_all_sites.return_value = ["std_gov", "ahbz"]
        self.assertEqual(self.handler.get_query_sites(), ["std_gov", "ahbz"])

    # ── get_site_adapter ──

    def test_get_site_adapter(self):
        mock_adapter = MagicMock()
        self.core.query_engine.get_adapter.return_value = mock_adapter
        self.assertIs(self.handler.get_site_adapter("std_gov"), mock_adapter)

    # ── get_site_cooldown ──

    def test_get_site_cooldown(self):
        self.core.query_engine.get_site_cooldown.return_value = 5.0
        self.assertEqual(self.handler.get_site_cooldown("std_gov"), 5.0)

    # ── get_query_status ──

    def test_get_query_status(self):
        self.core.query_engine.is_query_running.return_value = False
        self.core.query_engine.get_overflow_count.return_value = 0
        self.core.query_engine.get_csres_status.return_value = {"is_active": False}
        self.core.query_engine.is_idle.return_value = True

        status = self.handler.get_query_status()
        self.assertFalse(status["is_running"])
        self.assertEqual(status["overflow_count"], 0)
        self.assertFalse(status["csres_active"])
        self.assertTrue(status["is_idle"])

    # ── get_adapter_report ──

    def test_get_adapter_report(self):
        self.core.db.get_adapter_stats_all.return_value = [{"site": "std_gov", "success": 10}]
        result = self.handler.get_adapter_report()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["site"], "std_gov")

    # ── set_pause_event ──

    def test_set_pause_event(self):
        ev = MagicMock()
        self.handler.set_pause_event(ev)
        self.core.query_engine.set_pause_event.assert_called_once_with(ev)


if __name__ == "__main__":
    unittest.main()
