"""AnnounceCrawler tests -- check_all / check_filtered pipeline."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pilotstd.announce.crawler_service import AnnounceCrawler
from pilotstd.announce.persistence import AnnouncePersistence


@pytest.fixture
def mock_persistence():
    p = MagicMock(spec=AnnouncePersistence)
    p.get_checkpoint.return_value = None
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
