"""公告 checkpoint 不得跨过详情抓取失败项（D-13 同批修复的公告漏抓根因）。"""

from __future__ import annotations

from unittest.mock import MagicMock

from pilotstd.announcement.engine import AnnounceEngine


class _Adapter:
    standard_type = "gb"
    source_site = "announcement_gb"
    standard_category = "NationalStd"

    def __init__(self, failed: list[str], items: list[dict]) -> None:
        self.failed_notice_dates = failed
        self._items = items

    def fetch_announcements(self, **kwargs):
        return self._items


def _engine() -> AnnounceEngine:
    adapter = _Adapter([], [])
    eng = AnnounceEngine([adapter], matcher=MagicMock())
    eng._matcher._get_complete_pids.return_value = set()
    eng._matcher.match_and_update.return_value = {"matched": 1, "updated": 0, "details": []}
    return eng


def test_checkpoint_stops_before_earliest_failure() -> None:
    adapter = _Adapter(
        ["2026-08-12"],
        [{"notice_date": "2026-08-20", "_pid": "p2"}],
    )
    eng = AnnounceEngine([adapter], matcher=MagicMock())
    eng._matcher._get_complete_pids.return_value = set()
    eng._matcher.match_and_update.return_value = {"matched": 1, "updated": 0, "details": []}

    result = eng._check_one_adapter(adapter, "")

    assert result["last_notice_date"] == "2026-08-11"
    assert result["checkpoint_force"] is True


def test_checkpoint_uses_max_when_no_failure() -> None:
    adapter = _Adapter(
        [],
        [
            {"notice_date": "2026-08-12", "_pid": "p1"},
            {"notice_date": "2026-08-20", "_pid": "p2"},
        ],
    )
    eng = AnnounceEngine([adapter], matcher=MagicMock())
    eng._matcher._get_complete_pids.return_value = set()
    eng._matcher.match_and_update.return_value = {"matched": 1, "updated": 0, "details": []}

    result = eng._check_one_adapter(adapter, "")

    assert result["last_notice_date"] == "2026-08-20"
    assert "checkpoint_force" not in result


def test_write_checkpoint_force_regresses_but_normal_write_does_not() -> None:
    from pilotstd.announce.persistence import AnnouncePersistence

    persistence = object.__new__(AnnouncePersistence)
    persistence._query_one = MagicMock(return_value={"last_notice_date": "2026-09-01"})
    persistence._exec = MagicMock()

    persistence.write_checkpoint("announcement_gb", "2026-08-11")
    persistence._exec.assert_not_called()

    persistence.write_checkpoint("announcement_gb", "2026-08-11", force=True)
    params = persistence._exec.call_args.args[1]
    assert params[0] == "announcement_gb"
    assert params[2] == "2026-08-11"


def test_detail_failure_records_notice_date_for_checkpoint() -> None:
    from pilotstd.announcement.base import BaseAnnounceCrawler

    class _Crawler(BaseAnnounceCrawler):
        standard_type = "gb"
        site_name = "test-site"
        _list_url = "http://example.invalid/list"
        _detail_url = "http://example.invalid/detail"

    crawler = _Crawler()
    crawler._fetch_detail = lambda pid: None

    result = crawler._process_one_detail(
        {"pid": "p1", "notice_date": "2026-08-12"}, None, lambda pid: None
    )

    assert result == []
    assert crawler.failed_notice_dates == ["2026-08-12"]
