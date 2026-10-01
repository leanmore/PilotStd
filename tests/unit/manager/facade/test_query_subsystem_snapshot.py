"""QuerySubsystem Phase 0/1 行为快照测试。

交叉调用图谱：
  _finalize_query → self._classify_after_query
  _finalize_query → self.record_pending
  _finalize_query → self._report_query_summary
  _query → self._query_via_engine / self._query_via_cache
  _query → self._finalize_query
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from pilotstd.manager.facade._query_subsystem import QuerySubsystem
from pilotstd.query.models import BatchQueryStats, QueryResult


@pytest.fixture
def core():
    c = MagicMock()
    c.cfg = MagicMock()
    c.query_engine = MagicMock()
    c.query_engine.query_standards.return_value = []
    c.notification_mgr = MagicMock()
    c.classifier = MagicMock()
    c.pending_svc = MagicMock()
    c.parsed_results = []
    c.queried_items = []
    c.query_results = []
    c.download_list = []
    c.expire_list = []
    c.pending_list = []
    return c


@pytest.fixture
def qs(core):
    return QuerySubsystem(core)


class TestBuildResultFromCache:

    def test_full_cache_data(self):
        result = QuerySubsystem._build_result_from_cache("GB 123-2020", {
            "standard_name": "测试标准", "status": "现行",
            "replaces": "GB 122-2010", "is_adopted": False,
            "match_status": "exact", "hcno": "ABC123",
        })
        assert result.standard_number == "GB 123-2020"
        assert result.standard_name == "测试标准"
        assert result.source_site == "web_announcement_match"
        assert result.hcno == "ABC123"

    def test_empty_cache_returns_defaults(self):
        result = QuerySubsystem._build_result_from_cache("GB 999", {})
        assert result.standard_number == "GB 999"
        assert result.standard_name == ""

    def test_none_cache_handled(self):
        result = QuerySubsystem._build_result_from_cache("GB 999", None)
        assert result.standard_number == "GB 999"


class TestReportQuerySummary:

    def test_summary_with_results(self, qs, caplog):
        caplog.set_level(logging.INFO)
        stats = BatchQueryStats(total=3, found=2, exact=2)
        items = [MagicMock(logical_code="GB") for _ in range(3)]
        results = [
            QueryResult(standard_number="GB 1-2020", standard_name="标准一",
                        source_site="std_gov", match_status="exact"),
            QueryResult(standard_number="GB 2-2020", standard_name="标准二",
                        source_site="std_gov", match_status="exact"),
            QueryResult(standard_number="GB 3-2020", standard_name="",
                        match_status="older"),
        ]
        qs._report_query_summary(stats, items, results)
        assert "查询完成" in caplog.text

    def test_summary_empty_results(self, qs, caplog):
        caplog.set_level(logging.INFO)
        stats = BatchQueryStats(total=0, found=0, exact=0)
        qs._report_query_summary(stats, [], [])
        assert "查询完成" in caplog.text

    def test_summary_with_pending_by_reason(self, qs, caplog):
        caplog.set_level(logging.INFO)
        stats = BatchQueryStats(total=2, found=0, exact=0)
        items = [MagicMock(logical_code="GB") for _ in range(2)]
        results = [
            QueryResult(standard_number="GB 1-2020", standard_name="", match_status="older"),
            QueryResult(standard_number="GB 2-2020", standard_name="", match_status="code_only"),
        ]
        qs._report_query_summary(stats, items, results)
        assert "待确认" in caplog.text


class TestClassifyAfterQuery:

    def test_classify_called(self, qs, core):
        items = [MagicMock(logical_code="GB")]
        results = [QueryResult(standard_number="GB 1-2020", standard_name="测试")]
        qs._classify_after_query(items, results)
        core.classifier.classify.assert_called_once()


class TestResolveReplaces:

    def test_resolve_delegates(self, qs, core):
        core.classifier.resolve_replaces.return_value = "GB 999-2020"
        result = qs._resolve_replaces("GB 100-2010")
        assert result == "GB 999-2020"


class TestQueryViaEngine:

    def test_engine_called_with_tuples(self, qs, core):
        p = MagicMock()
        p.logical_code = "GB"
        p.number = 123
        p.year = 2020
        p.std_name = "测试"
        p.part = None
        p.num_prefix = ""
        core.query_engine.query_standards.return_value = [
            QueryResult(standard_number="GB 123-2020", standard_name="结果")
        ]
        results = qs._query_via_engine([p], None, site="std_gov", force_refresh=True)
        assert len(results) == 1
        assert results[0].standard_name == "结果"

    def test_engine_returns_empty(self, qs, core):
        results = qs._query_via_engine([], None)
        assert results == []


class TestQueryIntegrationPaths:
    """原 4 处永久 skip（T-29／R13-1）的真实替代覆盖——全部用 mock/补丁驱动，不触网。"""

    def test_query_announcement_match(self, qs, core, monkeypatch):
        """公告缓存查询：命中／未命中／HTTP 异常降级／未配置 api_key 不发请求。"""
        core.cfg = {
            "query.announcement_url": "http://api.test",
            "network.timeout": 5,
            "query.announcement_api_key": "k",
        }
        resp = MagicMock()
        resp.json.return_value = {"found": True, "data": {"standard_name": "测试标准"}, "cached_at": "2026-01-01"}
        monkeypatch.setattr("pilotstd.manager.facade._query_subsystem.requests.get", lambda *a, **kw: resp)

        hit = qs._query_announcement_match("GB 1-2020")
        assert hit == {"data": {"standard_name": "测试标准"}, "cached_at": "2026-01-01"}

        resp.json.return_value = {"found": False}
        assert qs._query_announcement_match("GB 2-2020") is None

        def _timeout(*a, **kw):
            raise requests.exceptions.Timeout("timeout")

        monkeypatch.setattr("pilotstd.manager.facade._query_subsystem.requests.get", _timeout)
        assert qs._query_announcement_match("GB 3-2020") is None

        core.cfg["query.announcement_api_key"] = "   "
        called: list[int] = []
        monkeypatch.setattr("pilotstd.manager.facade._query_subsystem.requests.get", lambda *a, **kw: called.append(1))
        assert qs._query_announcement_match("GB 4-2020") is None
        assert called == [], "未配置 api_key 时不得发起 HTTP 请求"

    def test_query_via_cache(self, qs, core, monkeypatch):
        """公告缓存优先：命中走缓存（source_site=web_announcement_match）、未命中降级引擎并回填原索引。"""
        hit = MagicMock(logical_code="GB", number=1, year=2020, part=None, std_name="", num_prefix="")
        miss = MagicMock(logical_code="GB", number=2, year=2020, part=None, std_name="", num_prefix="")
        monkeypatch.setattr(
            qs,
            "_query_announcement_match",
            lambda std_num: {"data": {"standard_name": "缓存命中"}} if std_num.startswith("GB 1") else None,
        )

        def _engine(tuples, result_callback=None, progress_callback=None):
            live = QueryResult(standard_number="GB 2-2020", standard_name="实时结果")
            if result_callback:
                result_callback(0, live)
            return [live]

        core.query_engine.query_standards.side_effect = _engine
        seen: list[tuple[int, str]] = []
        results = qs._query_via_cache([hit, miss], lambda i, r: seen.append((i, r.standard_name)))

        assert results[0].standard_name == "缓存命中"
        assert results[0].source_site == "web_announcement_match"
        assert results[1].standard_name == "实时结果"
        assert results[1].source == "live_fallback"
        assert seen == [(0, "缓存命中"), (1, "实时结果")]

    def test_finalize_query(self, qs, core):
        """收尾：统计口径（total/found/exact/downloadable）+ 失败通知 + 汇总通知 + 分类调用。"""
        items = [MagicMock(logical_code="GB"), MagicMock(logical_code="SH")]
        results = [
            QueryResult(standard_number="GB 1-2020", standard_name="甲", match_status="exact", is_downloadable=True),
            QueryResult(standard_number="SH 2-2020", standard_name="", error_message="超时"),
        ]
        returned, stats = qs._finalize_query(items, results)

        assert returned is results
        assert core.query_results is results
        # downloadable 计 2：QueryResult.is_downloadable 默认 True，失败项也计（与实现一致）
        assert (stats.total, stats.found, stats.exact, stats.downloadable) == (2, 1, 1, 2)
        core.classifier.classify.assert_called_once()
        events = [c.args[0] for c in core.notification_mgr.send_event.call_args_list]
        assert "query_failed" in events
        assert "batch_query_summary" in events

    def test_finalize_query_empty_notifies_and_records_pending(self, qs, core, monkeypatch):
        """全部未命中 → query_empty 通知；pending_list 非空 → 触发 record_pending。"""
        core.pending_list = [MagicMock()]
        recorded: list[list[Any]] = []
        monkeypatch.setattr(qs, "record_pending", lambda pending_items: recorded.append(pending_items))

        _, stats = qs._finalize_query(
            [MagicMock(logical_code="GB")],
            [QueryResult(standard_number="GB 1-2020", standard_name="")],
        )

        assert stats.total == 1 and stats.found == 0
        events = [c.args[0] for c in core.notification_mgr.send_event.call_args_list]
        assert "query_empty" in events
        assert recorded and len(recorded[0]) == 1

    def test_query_main(self, qs, core, monkeypatch):
        """query() 走公告缓存分支，并正确接线 progress_callback(count, total)。"""
        core.cfg = {"query.use_announcement_match": True}
        item = MagicMock(logical_code="GB", number=1, year=2020, part=None, std_name="", num_prefix="")
        core.parsed_results = [item]
        captured: dict[str, Any] = {}

        def _cache(items, result_callback, progress_callback=None):
            captured["items"] = items
            captured["progress"] = progress_callback
            return [QueryResult(standard_number="GB 1-2020", standard_name="缓存")]

        monkeypatch.setattr(qs, "_query_via_cache", _cache)
        progress: list[tuple[int, int]] = []
        results, stats = qs.query(progress_callback=lambda c, t: progress.append((c, t)))

        assert captured["items"] == [item]
        assert core.queried_items == [item]
        assert stats.total == 1 and results[0].standard_name == "缓存"
        assert captured["progress"] is not None
        captured["progress"](1)
        assert progress == [(1, 1)]


class TestQueryBasic:

    def test_query_with_explicit_site_uses_engine(self, qs, core):
        p = MagicMock()
        p.logical_code = "GB"
        p.number = 123
        p.year = 2020
        p.std_name = ""
        p.part = None
        p.num_prefix = ""
        core.parsed_results = [p]
        core.query_engine.query_standards.return_value = [
            QueryResult(standard_number="GB 123-2020", standard_name="结果")
        ]
        results, stats = qs.query(site="std_gov")
        assert stats.total == 1
        assert stats.found == 1

    def test_query_with_empty_parsed_list(self, qs, core):
        core.parsed_results = []
        core.query_engine.query_standards.return_value = []
        results, stats = qs.query()
        assert stats.total == 0
        assert len(results) == 0

    def test_query_stream_delegates(self, qs, core):
        p = MagicMock()
        p.logical_code = "GB"
        p.number = 1
        p.year = 2020
        p.std_name = ""
        p.part = None
        p.num_prefix = ""
        core.query_engine.query_standards.return_value = [
            QueryResult(standard_number="GB 1-2020", standard_name="OK")
        ]
        results, stats = qs.query_stream([p], site="std_gov")
        assert stats.total == 1
        assert results[0].standard_name == "OK"

    def test_query_force_refresh_passes_through(self, qs, core):
        p = MagicMock()
        p.logical_code = "SH"
        p.number = 56
        p.year = 2021
        p.std_name = ""
        p.part = None
        p.num_prefix = ""
        core.parsed_results = [p]
        core.query_engine.query_standards.return_value = [
            QueryResult(standard_number="SH 56-2021", standard_name="行标")
        ]
        results, stats = qs.query(force_refresh=True, site="std_gov")
        call_kwargs = core.query_engine.query_standards.call_args
        assert call_kwargs[1]["force_refresh"] is True
