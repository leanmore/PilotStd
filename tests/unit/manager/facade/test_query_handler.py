"""_query.py (QueryHandler) 覆盖率补齐 — 目标: 54% → 90%+"""

from unittest.mock import MagicMock, patch

import pytest

from pilotstd.manager.facade._query import QueryHandler
from pilotstd.query.models import QueryResult


@pytest.fixture
def handler(mock_core):
    return QueryHandler(mock_core)


class TestGetStageQueue:
    def test_download_stage(self, handler, mock_core):
        mock_core.download_list = [MagicMock()]
        result = handler.get_stage_queue("download")
        assert len(result) == 1

    def test_expire_stage(self, handler, mock_core):
        mock_core.expire_list = [MagicMock(), MagicMock()]
        result = handler.get_stage_queue("expire")
        assert len(result) == 2

    def test_pending_stage(self, handler, mock_core):
        mock_core.pending_list = [MagicMock()]
        result = handler.get_stage_queue("pending")
        assert len(result) == 1

    def test_default_stage_falls_back_to_queried(self, handler, mock_core):
        mock_core.queried_items = [MagicMock()]
        result = handler.get_stage_queue("unknown_stage")
        assert len(result) == 1

    def test_default_stage_falls_back_to_parsed_when_queried_none(self, handler, mock_core):
        mock_core.queried_items = None
        mock_core.parsed_results = [MagicMock(), MagicMock()]
        result = handler.get_stage_queue("unknown_stage")
        assert len(result) == 2


class TestGetStageSummary:
    def test_returns_all_counts(self, handler, mock_core):
        mock_core.download_list = [1]
        mock_core.expire_list = [1, 2]
        mock_core.pending_list = [1, 2, 3]
        mock_core.queried_items = [1, 2, 3, 4]

        result = handler.get_stage_summary()
        assert result["download"] == 1
        assert result["expire"] == 2
        assert result["pending"] == 3
        assert result["total"] == 4

    def test_total_falls_back_to_parsed(self, handler, mock_core):
        mock_core.queried_items = None
        mock_core.parsed_results = [1, 2]
        result = handler.get_stage_summary()
        assert result["total"] == 2


class TestGetQueryStatus:
    def test_returns_status_dict(self, handler, mock_core):
        result = handler.get_query_status()
        assert result["is_running"] is False
        assert result["overflow_count"] == 0
        assert result["csres_active"] is True
        assert result["is_idle"] is True


class TestPendingDelegations:
    def test_resolve_pending(self, handler, mock_core):
        handler.resolve_pending([{"id": 1}], "confirm")
        mock_core.pending_svc.resolve_pending.assert_called_once_with(
            [{"id": 1}], "confirm"
        )

    def test_resolve_pending_by_numbers(self, handler, mock_core):
        handler.resolve_pending_by_numbers(["GB 1-2020"], "dismiss")
        mock_core.pending_svc.resolve_pending_by_numbers.assert_called_once_with(
            ["GB 1-2020"], "dismiss"
        )

    def test_get_pending_items(self, handler, mock_core):
        mock_core.pending_svc.get_pending_items.return_value = [{"id": 1}]
        assert handler.get_pending_items() == [{"id": 1}]

    def test_increment_requery_count(self, handler, mock_core):
        mock_core.pending_svc.increment_requery_count.return_value = 3
        assert handler.increment_requery_count("GB 1") == 3

    def test_is_requery_exhausted(self, handler, mock_core):
        mock_core.pending_svc.is_requery_exhausted.return_value = True
        assert handler.is_requery_exhausted("GB 1") is True


class TestStaticMethods:
    def test_build_result_from_cache(self):
        with patch(
            "pilotstd.manager.facade._query.QuerySubsystem._build_result_from_cache",
            return_value=QueryResult(standard_number="GB 1"),
        ) as mock_build:
            result = QueryHandler._build_result_from_cache("GB 1", {"name": "x"})
            mock_build.assert_called_once_with("GB 1", {"name": "x"})
            assert result.standard_number == "GB 1"

    def test_parse_std_number(self):
        with patch(
            "pilotstd.manager.facade._query.QuerySubsystem._parse_std_number",
            return_value=("GB", 1234),
        ) as mock_parse:
            code, num = QueryHandler._parse_std_number("GB 1234-2020")
            mock_parse.assert_called_once_with("GB 1234-2020")
            assert code == "GB"
            assert num == 1234


class TestGuiBridgeMethods:
    def test_query_by_numbers(self, handler, mock_core):
        handler.query_by_numbers(["GB 1-2020"], force_refresh=True, preferred_site="ahbz")
        mock_core.scheduled_svc.query_by_numbers.assert_called_once_with(
            ["GB 1-2020"], True, "ahbz"
        )

    def test_get_query_sites(self, handler, mock_core):
        assert handler.get_query_sites() == ["ahbz", "std_gov"]

    def test_get_site_cooldown(self, handler, mock_core):
        assert handler.get_site_cooldown("ahbz") == 1.5

    def test_set_pause_event(self, handler, mock_core):
        event = MagicMock()
        handler.set_pause_event(event)
        mock_core.query_engine.set_pause_event.assert_called_once_with(event)

    def test_get_quota_info(self, handler, mock_core):
        result = handler.get_quota_info()
        assert result == {"used": 10, "total": 100}

    def test_plan_batch(self, handler, mock_core):
        result = handler.plan_batch(50)
        assert result == [("ahbz", 5)]
        mock_core.query_engine.plan_batch.assert_called_once_with(50)

    def test_mark_manual_required(self, handler, mock_core):
        handler.mark_manual_required("GB 1")
        mock_core.pending_svc.mark_manual_required.assert_called_once_with("GB 1")

    def test_get_requery_count(self, handler, mock_core):
        assert handler.get_requery_count("GB 1") == 0

    def test_query_local_cache(self, handler, mock_core):
        handler.query_local_cache([])
        mock_core.pending_svc.query_local_cache.assert_called_once_with([])

    def test_get_adapter_report(self, handler, mock_core):
        assert handler.get_adapter_report() == []


# === Added for 100% coverage (delegation methods, L47-73, L149) ===


class TestQueryHandlerDelegations:
    """覆盖 QueryHandler → QuerySubsystem 的 7 个委托透传方法。"""

    @pytest.fixture(autouse=True)
    def _mock_qs(self, handler):
        """替换 handler._qs 为 mock，隔离 QuerySubsystem 依赖。"""
        from unittest.mock import MagicMock

        handler._qs = MagicMock()
        return handler

    def test_query_delegates(self, handler):
        """query() → 委托 _qs.query (L47)。"""
        parsed = [MagicMock()]
        handler._qs.query.return_value = ([], MagicMock(found=5))
        handler.query(parsed, force_refresh=True)
        handler._qs.query.assert_called_once()

    def test_query_stream_delegates(self, handler):
        """query_stream() → 委托 _qs.query_stream (L58)。"""
        parsed = [MagicMock()]
        handler._qs.query_stream.return_value = ([], MagicMock(found=2))
        handler.query_stream(parsed)
        handler._qs.query_stream.assert_called_once()

    def test_record_pending_delegates(self, handler):
        """record_pending() → 委托 _qs.record_pending (L61)。"""
        items = [MagicMock()]
        handler.record_pending(items)
        handler._qs.record_pending.assert_called_once_with(items)

    def test_query_announcement_match_delegates(self, handler):
        """_query_announcement_match() → 委托 _qs (L64)。"""
        handler._qs._query_announcement_match.return_value = {"matched": True}
        r = handler._query_announcement_match("GB 1-2020")
        assert r == {"matched": True}
        handler._qs._query_announcement_match.assert_called_once_with("GB 1-2020")

    def test_classify_after_query_delegates(self, handler):
        """_classify_after_query() → 委托 _qs (L67)。"""
        handler._classify_after_query([], [])
        handler._qs._classify_after_query.assert_called_once()

    def test_resolve_replaces_delegates(self, handler):
        """_resolve_replaces() → 委托 _qs (L70)。"""
        handler._qs._resolve_replaces.return_value = "GB/T 9999-2025"
        r = handler._resolve_replaces("GB/T 1234-2015")
        assert r == "GB/T 9999-2025"
        handler._qs._resolve_replaces.assert_called_once_with("GB/T 1234-2015")

    def test_report_query_summary_delegates(self, handler):
        """_report_query_summary() → 委托 _qs (L73)。"""
        handler._report_query_summary(MagicMock(), [], [])
        handler._qs._report_query_summary.assert_called_once()

    def test_get_site_adapter_delegates(self, handler, mock_core):
        """get_site_adapter() → 委托 query_engine (L149)。"""
        mock_adapter = MagicMock()
        mock_core.query_engine.get_adapter.return_value = mock_adapter
        assert handler.get_site_adapter("ahbz") is mock_adapter
