"""AnnounceCrawler tests -- check_all / check_filtered pipeline."""
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

import pytest

from pilotstd.announce.crawler_service import AnnounceCrawler, query_announcement_stats


@pytest.fixture
def mock_persistence():
    p = MagicMock()
    p.get_checkpoint.return_value = None
    p._db = MagicMock()
    return p


@pytest.fixture
def crawler(mock_persistence):
    fi = MagicMock()
    fi._db = MagicMock()
    return AnnounceCrawler(file_index=fi, persistence=mock_persistence, ocr_config={})


def _mock_adapter(std_type, source_site, site_name):
    a = MagicMock()
    a.standard_type = std_type
    a.source_site = source_site
    a.site_name = site_name
    return a


def _patch_engine(crawler, adapters, check_one_return):
    """Replace crawler._engine with a mock that has the given adapters/check_one."""
    mock_engine = MagicMock()
    mock_engine.adapters = adapters
    mock_engine.check_one.return_value = check_one_return
    crawler._engine = mock_engine


class TestCheckAll:
    def test_single_adapter_success(self, crawler, mock_persistence):
        adapter = _mock_adapter("gb", "samr_gb", "GB site")
        _patch_engine(crawler, [adapter], {
            "matched": 3, "updated": 1, "last_notice_date": "2024-06-15",
        })
        result = crawler.check_all()

        assert result["matched"] == 3
        assert result["updated"] == 1
        assert result["errors"] == []
        mock_persistence.write_checkpoint.assert_called_with("samr_gb", "2024-06-15")

    def test_adapter_error_handled(self, crawler, mock_persistence):
        adapter = _mock_adapter("hb", "samr_hb", "HB site")
        _patch_engine(crawler, [adapter], {"error": "timeout"})
        result = crawler.check_all()

        assert result["matched"] == 0
        assert len(result["errors"]) == 1
        assert result["errors"][0]["error"] == "timeout"
        mock_persistence.record_failure.assert_called_once()

    def test_empty_items_handled(self, crawler, mock_persistence):
        adapter = _mock_adapter("db", "samr_db", "DB site")
        _patch_engine(crawler, [adapter], {
            "matched": 0, "updated": 0, "last_notice_date": "",
        })
        result = crawler.check_all()

        assert result["matched"] == 0
        assert result["errors"] == []

    def test_result_includes_stats_fields(self, crawler, mock_persistence):
        """阶段二：check_all 返回分类统计字段（gb/hb/db/total_standards）。"""
        adapter = _mock_adapter("gb", "samr_gb", "GB site")
        _patch_engine(crawler, [adapter], {
            "matched": 2, "updated": 1, "last_notice_date": "2024-06-15",
        })
        result = crawler.check_all()

        assert "gb_count" in result
        assert "hb_count" in result
        assert "db_count" in result
        assert "total_standards" in result
        assert result["total_announcements"] == 3


class TestQueryAnnouncementStats:
    """阶段二：query_announcement_stats 分组计数（sqlite3 双后端）。"""

    def _make_db(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS announcement_record (
    id INTEGER,
    source_site TEXT NOT NULL,
    pid TEXT NOT NULL,
    announce_no TEXT,
    standard_number TEXT NOT NULL,
    std_name TEXT,
    publish_date TEXT,
    fetched_at TEXT NOT NULL,
    matched INTEGER DEFAULT 0,
    source_version TEXT DEFAULT 'initial',
    data_state TEXT DEFAULT 'fresh',
    last_accessed_at TEXT,
    announcement_title TEXT,
    standard_count INTEGER,
    announcement_id INTEGER,
    row_index INTEGER,
    implement_date TEXT,
    expiry_date TEXT,
    superseded_by TEXT,
    status TEXT DEFAULT 'draft',
    confidence REAL DEFAULT 0.0,
    raw_text TEXT,
    parser_engine TEXT,
    approved_by INTEGER,
    approved_at TEXT,
    updated_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    source_type TEXT DEFAULT '网页解析',
    standard_type TEXT NOT NULL DEFAULT 'Unknown'
);"""
        )
        conn.execute(
            "INSERT INTO announcement_record (pid, announce_no, standard_number, source_site, fetched_at) "
            "VALUES ('p1','gb公告1','GB/T 1','announcement_gb','2026-08-19T10:00:00')"
        )
        conn.execute(
            "INSERT INTO announcement_record (pid, announce_no, standard_number, source_site, fetched_at) "
            "VALUES ('p1','gb公告1','GB/T 2','announcement_gb','2026-08-19T10:00:01')"
        )
        conn.execute(
            "INSERT INTO announcement_record (pid, announce_no, standard_number, source_site, fetched_at) "
            "VALUES ('p2','hb公告2','JB/T 1','announcement_hb','2026-08-19T10:00:02')"
        )
        conn.execute(
            "INSERT INTO announcement_record (pid, announce_no, standard_number, source_site, fetched_at) "
            "VALUES ('p3','db公告3','DB/T 1','announcement_db','2026-08-19T09:00:00')"
        )
        return conn

    def test_grouped_counts_since(self):
        conn = self._make_db()
        try:
            stats = query_announcement_stats(conn, "2026-08-19T10:00:00")
            # 公告数按 announce_no 去重；db 公告早于 since 不计入
            assert stats["total_announcements"] == 2
            assert stats["total_standards"] == 3
            assert stats["gb_count"] == 1
            assert stats["gb_standards"] == 2
            assert stats["hb_count"] == 1
            assert stats["hb_standards"] == 1
            assert stats["db_count"] == 0
            assert stats["db_standards"] == 0
        finally:
            conn.close()

    def test_db_failure_returns_zeros(self):
        db = MagicMock()
        db.fetchall.side_effect = RuntimeError("no such table")
        stats = query_announcement_stats(db, "2026-08-19T10:00:00")
        assert stats["total_announcements"] == 0
        assert stats["gb_count"] == 0


class TestCheckFiltered:
    def test_filter_by_types(self, crawler):
        gb = _mock_adapter("gb", "samr_gb", "GB")
        hb = _mock_adapter("hb", "samr_hb", "HB")
        _patch_engine(crawler, [gb, hb], {"matched": 1, "updated": 0})

        result = crawler.check_filtered(types=["gb"])

        assert list(result.keys()) == ["gb"]
        crawler._engine.check_one.assert_called_once()

    def test_filter_by_since_date(self, crawler):
        adapter = _mock_adapter("gb", "samr_gb", "GB")
        _patch_engine(crawler, [adapter], {"matched": 0, "updated": 0})

        crawler.check_filtered(since_date="2024-01-01")

        crawler._engine.check_one.assert_called_once_with(
            "gb", since_date="2024-01-01", ocr_provider=None
        )

    def test_filter_all_types(self, crawler):
        gb = _mock_adapter("gb", "samr_gb", "GB")
        hb = _mock_adapter("hb", "samr_hb", "HB")
        _patch_engine(crawler, [gb, hb], {"matched": 2, "updated": 1})

        result = crawler.check_filtered()

        assert set(result.keys()) == {"gb", "hb"}
        assert crawler._engine.check_one.call_count == 2
