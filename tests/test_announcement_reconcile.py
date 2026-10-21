"""P2 防漏：公告入库条数对账。"""

from __future__ import annotations

from unittest.mock import MagicMock

from pilotstd.announcement.reconcile import find_announcement_count_mismatches


def test_returns_mismatches_with_diff() -> None:
    db = MagicMock()
    db.fetchall.return_value = [
        {"source_site": "announcement_hb", "announce_no": "2026年第9号", "declared": 588, "actual": 555},
        {"source_site": "announcement_gb", "announce_no": "2026年第39号", "declared": 100, "actual": 99},
    ]

    rows = find_announcement_count_mismatches(db)

    assert rows == [
        {
            "source_site": "announcement_hb",
            "announce_no": "2026年第9号",
            "declared": 588,
            "actual": 555,
            "diff": -33,
        },
        {
            "source_site": "announcement_gb",
            "announce_no": "2026年第39号",
            "declared": 100,
            "actual": 99,
            "diff": -1,
        },
    ]
    sql = db.fetchall.call_args.args[0]
    assert "TRIM(announce_no)" in sql
    assert "HAVING" in sql


def test_empty_result_returns_empty_list() -> None:
    db = MagicMock()
    db.fetchall.return_value = []
    assert find_announcement_count_mismatches(db) == []
