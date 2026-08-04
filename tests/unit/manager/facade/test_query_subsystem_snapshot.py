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
from unittest.mock import MagicMock

import pytest

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
        p.logical_code = "GB"; p.number = 123; p.year = 2020
        p.std_name = "测试"; p.part = None; p.num_prefix = ""
        core.query_engine.query_standards.return_value = [
            QueryResult(standard_number="GB 123-2020", standard_name="结果")
        ]
        results = qs._query_via_engine([p], None, site="std_gov", force_refresh=True)
        assert len(results) == 1
        assert results[0].standard_name == "结果"

    def test_engine_returns_empty(self, qs, core):
        results = qs._query_via_engine([], None)
        assert results == []


class TestSkippedIntegrationPaths:

    @pytest.mark.skip(reason="依赖 HTTP 请求（requests.get）")
    def test_query_announcement_match(self):
        pass

    @pytest.mark.skip(reason="依赖 HTTP + query_engine 降级")
    def test_query_via_cache(self):
        pass

    @pytest.mark.skip(reason="修改 5+ core 状态 + 通知发送")
    def test_finalize_query(self):
        pass

    @pytest.mark.skip(reason="query() 入口聚合")
    def test_query_main(self):
        pass


class TestQueryBasic:

    def test_query_with_explicit_site_uses_engine(self, qs, core):
        p = MagicMock()
        p.logical_code = "GB"; p.number = 123; p.year = 2020
        p.std_name = ""; p.part = None; p.num_prefix = ""
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
        p.logical_code = "GB"; p.number = 1; p.year = 2020
        p.std_name = ""; p.part = None; p.num_prefix = ""
        core.query_engine.query_standards.return_value = [
            QueryResult(standard_number="GB 1-2020", standard_name="OK")
        ]
        results, stats = qs.query_stream([p], site="std_gov")
        assert stats.total == 1
        assert results[0].standard_name == "OK"

    def test_query_force_refresh_passes_through(self, qs, core):
        p = MagicMock()
        p.logical_code = "SH"; p.number = 56; p.year = 2021
        p.std_name = ""; p.part = None; p.num_prefix = ""
        core.parsed_results = [p]
        core.query_engine.query_standards.return_value = [
            QueryResult(standard_number="SH 56-2021", standard_name="行标")
        ]
        results, stats = qs.query(force_refresh=True, site="std_gov")
        call_kwargs = core.query_engine.query_standards.call_args
        assert call_kwargs[1]["force_refresh"] is True
