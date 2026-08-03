"""classifier.py coverage completion -- target: 82% -> 98%+."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from pilotstd.manager.classifier import QueryClassifier


def _make_clf(adapters=None, quota_tracker=None, query_engine=None, router=None):
    return QueryClassifier(
        router=router or MagicMock(),
        query_adapters=adapters or [],
        quota_tracker=quota_tracker or MagicMock(),
        query_engine=query_engine or MagicMock(),
    )


def _make_parsed(logical_code="GB/T", full_number="GB/T 1234-2020"):
    p = MagicMock()
    p.logical_code = logical_code
    p.get_full_number.return_value = full_number
    p._replacement_number = ""
    p.found_replaces = ""
    return p


def _make_result(status="废止", replaces="", match_status="",
                 standard_number="GB/T 1234-2020"):
    r = MagicMock()
    r.status = status
    r.replaces = replaces
    r.match_status = match_status
    r.standard_number = standard_number
    return r


def _make_adapter(site_name, supports=True, found=True,
                  replaces_detail="GB/T 9999-2024"):
    a = MagicMock()
    a.site_name = site_name
    a.supports_replaces_detail = supports
    result = MagicMock()
    result.is_found.return_value = found
    a.query_with_strategy.return_value = result if found else None
    a.fetch_replaces_detail.return_value = replaces_detail if found else ""
    return a


PARSE_PATCH = "pilotstd.core.std_utils.parse_std_number"


# -- classify() public API (L81-86) -----------------------------------

class TestClassify:
    @patch.object(QueryClassifier, "_dispatch_by_router")
    @patch.object(QueryClassifier, "_resolve_cross_site_replaces")
    @patch.object(QueryClassifier, "_write_back_results")
    def test_orchestrates_three_steps(self, mock_wb, mock_resolve, mock_dispatch):
        clf = _make_clf()
        items = [MagicMock()]
        results = [MagicMock()]
        dl, el, pl = [], [], []
        notif = MagicMock()
        clf.classify(results, items, dl, el, pl, notification_mgr=notif)
        mock_wb.assert_called_once_with(items, results)
        mock_resolve.assert_called_once_with(items, results, notif)
        mock_dispatch.assert_called_once_with(items, dl, el, pl)

    @patch.object(QueryClassifier, "_dispatch_by_router")
    @patch.object(QueryClassifier, "_resolve_cross_site_replaces")
    @patch.object(QueryClassifier, "_write_back_results")
    def test_notification_mgr_defaults_none(self, mock_wb, mock_resolve, mock_dispatch):
        clf = _make_clf()
        clf.classify([], [], [], [], [])
        mock_resolve.assert_called_once_with([], [], None)


# -- _write_back_results (L90-101) ------------------------------------

class TestWriteBackResults:
    def test_all_fields_written(self):
        clf = _make_clf()
        p = MagicMock()
        r = MagicMock()
        r.status = "废止"
        r.match_status = "exact"
        r.replaces = "GB/T 9999-2024"
        r.is_adopted = True
        r.standard_name = "pressure vessel plate"
        r.split_into = "GB/T 9999.1, GB/T 9999.2"
        r.publish_date = "2024-01-01"
        r.implementation_date = "2024-07-01"
        r.responsible_dept = "SAC"
        r.abolition_date = "2024-12-31"
        r.source_site = "std.sac.gov.cn"
        clf._write_back_results([p], [r])
        assert p.effect_status == "废止"
        assert p.match_status == "exact"
        assert p.found_replaces == "GB/T 9999-2024"
        assert p.is_adopted is True
        assert p.found_name == "pressure vessel plate"
        assert p.split_parts == "GB/T 9999.1, GB/T 9999.2"
        assert p.found_publish_date == "2024-01-01"
        assert p.found_impl_date == "2024-07-01"
        assert p.found_responsible_dept == "SAC"
        assert p.found_abolition_date == "2024-12-31"
        assert p.found_source_site == "std.sac.gov.cn"

    def test_handles_missing_attrs(self):
        clf = _make_clf()
        p = MagicMock()
        r = MagicMock(spec=["status"])
        r.status = "现行"
        clf._write_back_results([p], [r])
        assert p.effect_status == "现行"
        assert p.match_status == ""
        assert p.found_replaces == ""
        assert p.is_adopted is False
        assert p.found_name == ""


# -- C1-C2: parse_std_number (L49-54) ---------------------------------

class TestParseStdNumber:
    def test_normal_extraction(self):
        code, number = QueryClassifier.parse_std_number("GB/T 713.1-2023")
        assert code == "GB/T"
        assert number == 713

    def test_no_match_returns_none(self):
        assert QueryClassifier.parse_std_number("") == (None, None)


# -- C3-C4: _resolve_cross_site_replaces (L115-121) -------------------

class TestResolveCrossSiteReplaces:
    @patch.object(QueryClassifier, "resolve_replaces",
                  return_value="GB/T 9999-2024")
    def test_triggers_resolve_and_writes_back(self, mock_resolve):
        clf = _make_clf()
        p = _make_parsed()
        r = _make_result(status="废止", replaces="")
        clf._resolve_cross_site_replaces([p], [r])
        mock_resolve.assert_called_once_with("GB/T 1234-2020", None)
        assert r.replaces == "GB/T 9999-2024"

    @patch.object(QueryClassifier, "resolve_replaces",
                  return_value="GB/T 9999-2024")
    def test_replacement_set_when_not_in_results(self, mock_resolve):
        clf = _make_clf()
        p = _make_parsed()
        r = _make_result(status="废止", replaces="",
                         standard_number="QB/T 5555-2020")
        clf._resolve_cross_site_replaces([p], [r])
        assert p._replacement_number == "GB/T 9999-2024"
        assert p.found_replaces == "GB/T 9999-2024"

    @patch.object(QueryClassifier, "resolve_replaces",
                  return_value="GB/T 9999-2024")
    def test_not_set_when_already_in_results(self, mock_resolve):
        clf = _make_clf()
        p = _make_parsed()
        r = _make_result(status="废止", replaces="")
        r2 = _make_result(status="现行", standard_number="GB/T 9999-2024")
        clf._resolve_cross_site_replaces([p], [r, r2])
        assert r.replaces == "GB/T 9999-2024"
        assert p._replacement_number == ""

    def test_skips_when_replaces_present(self):
        clf = _make_clf()
        p = _make_parsed()
        r = _make_result(status="废止", replaces="GB/T 5555-2019")
        with patch.object(clf, "resolve_replaces") as mock_rr:
            clf._resolve_cross_site_replaces([p], [r])
            mock_rr.assert_not_called()

    @patch.object(QueryClassifier, "resolve_replaces", return_value="")
    def test_empty_continue_no_write_back(self, mock_rr):
        clf = _make_clf()
        p = _make_parsed()
        r = _make_result(status="被代替", replaces="")
        clf._resolve_cross_site_replaces([p], [r])
        assert r.replaces == ""


# -- C5-C7: resolve_replaces (L148-175) ------------------------------

class TestResolveReplaces:
    @patch(PARSE_PATCH)
    def test_single_adapter_success(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        a = _make_adapter("gb_site", found=True)
        engine = MagicMock()
        engine._use_cache = True
        engine._cache = MagicMock()
        clf = _make_clf(adapters=[a], query_engine=engine)
        result = clf.resolve_replaces("GB/T 1234-2020")
        assert result == "GB/T 9999-2024"
        engine._cache.put.assert_called_once()

    @patch(PARSE_PATCH)
    def test_multi_adapter_first_hit_stops(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        a1 = _make_adapter("a1", found=False)
        a2 = _make_adapter("a2", found=True,
                                replaces_detail="GB/T 8888-2023")
        a3 = _make_adapter("a3", found=True)
        clf = _make_clf(adapters=[a1, a2, a3])
        assert clf.resolve_replaces("GB/T 1234-2020") == "GB/T 8888-2023"
        a3.query_with_strategy.assert_not_called()

    @patch(PARSE_PATCH)
    def test_all_not_found_returns_empty(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        clf = _make_clf(adapters=[_make_adapter("a", found=False),
                                  _make_adapter("b", found=False)])
        assert clf.resolve_replaces("GB/T 1234-2020") == ""

    def test_quota_exhausted_skips(self):
        a = _make_adapter("gb_site", found=True)
        quota = MagicMock()
        quota.can_use_for_detail.return_value = False
        clf = _make_clf(adapters=[a], quota_tracker=quota)
        assert clf.resolve_replaces("GB/T 1234-2020") == ""
        a.query_with_strategy.assert_not_called()

    @patch(PARSE_PATCH)
    def test_adapter_exception_continues(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        a = MagicMock()
        a.site_name = "broken"
        a.supports_replaces_detail = True
        a.query_with_strategy.side_effect = RuntimeError("boom")
        clf = _make_clf(adapters=[a])
        assert clf.resolve_replaces("GB/T 1234-2020") == ""

    @patch(PARSE_PATCH)
    def test_no_cache_when_disabled(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        a = _make_adapter("gb_site", found=True)
        engine = MagicMock()
        engine._use_cache = False
        clf = _make_clf(adapters=[a], query_engine=engine)
        clf.resolve_replaces("GB/T 1234-2020")
        engine._cache.put.assert_not_called()

    @patch(PARSE_PATCH)
    def test_parse_returns_none_skips(self, mock_parse):
        mock_parse.return_value = None
        a = _make_adapter("gb_site")
        clf = _make_clf(adapters=[a])
        assert clf.resolve_replaces("INVALID") == ""

    @patch(PARSE_PATCH)
    def test_supports_replaces_detail_false_skips(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        a = MagicMock()
        a.site_name = "no_support"
        a.supports_replaces_detail = False
        clf = _make_clf(adapters=[a])
        assert clf.resolve_replaces("GB/T 1234-2020") == ""
        a.query_with_strategy.assert_not_called()


# -- C8: notification (L178-184) --------------------------------------

class TestReplacementNotification:
    @patch(PARSE_PATCH)
    def test_sends_notification(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        a = _make_adapter("gb_site", found=False)
        notif = MagicMock()
        clf = _make_clf(adapters=[a])
        clf.resolve_replaces("GB/T 1234-2020", notification_mgr=notif)
        notif.send_event.assert_called_once_with(
            "replacement_not_found",
            {"standard_number": "GB/T 1234-2020",
             "searched_sources": ["gb_site"]})

    @patch(PARSE_PATCH)
    def test_exception_swallowed(self, mock_parse):
        mock_parse.return_value = {"code": "GB/T", "number": 1234,
                                   "year": 2020, "num_prefix": ""}
        a = _make_adapter("gb_site", found=False)
        notif = MagicMock()
        notif.send_event.side_effect = RuntimeError("fail")
        clf = _make_clf(adapters=[a])
        assert clf.resolve_replaces("GB/T 1234-2020",
                                    notification_mgr=notif) == ""

    def test_no_notification_when_no_sources(self):
        notif = MagicMock()
        clf = _make_clf(adapters=[])
        clf.resolve_replaces("GB/T 1234-2020", notification_mgr=notif)
        notif.send_event.assert_not_called()


# -- _dispatch_by_router (L127-141) -----------------------------------

class TestDispatchByRouter:
    def test_expired_stage_status(self):
        p = MagicMock()
        router = MagicMock()
        router.apply_actions.return_value = {
            "download": [], "expire": [p], "pending": [],
            "organize": [], "normalize": []}
        clf = _make_clf(router=router)
        dl, el, pl = [], [], []
        clf._dispatch_by_router([p], dl, el, pl)
        assert p.stage_status == "expired"

    def test_pending_only_when_empty(self):
        p_has = MagicMock()
        p_has.stage_status = "already_set"
        p_empty = MagicMock()
        p_empty.stage_status = ""
        router = MagicMock()
        router.apply_actions.return_value = {
            "download": [], "expire": [],
            "pending": [p_has, p_empty],
            "organize": [], "normalize": []}
        clf = _make_clf(router=router)
        clf._dispatch_by_router([], [], [], [])
        assert p_has.stage_status == "already_set"
        assert p_empty.stage_status == "pending"

    def test_archive_ready(self):
        p_org = MagicMock()
        p_norm = MagicMock()
        router = MagicMock()
        router.apply_actions.return_value = {
            "download": [], "expire": [], "pending": [],
            "organize": [p_org], "normalize": [p_norm]}
        clf = _make_clf(router=router)
        clf._dispatch_by_router([], [], [], [])
        assert p_org.stage_status == "archive_ready"
        assert p_norm.stage_status == "archive_ready"

    def test_download_stage_status(self):
        p = MagicMock()
        router = MagicMock()
        router.apply_actions.return_value = {
            "download": [p], "expire": [], "pending": [],
            "organize": [], "normalize": []}
        clf = _make_clf(router=router)
        dl, el, pl = [], [], []
        clf._dispatch_by_router([p], dl, el, pl)
        assert p.stage_status == "download"
