"""测试 AnnounceEngine — check_all / check_one / _check_one_adapter 全分支。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilotstd.announcement.engine import AnnounceEngine


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.standard_type = "gb"
    adapter.source_site = "samr_gb"
    return adapter


@pytest.fixture
def mock_matcher():
    matcher = MagicMock()
    matcher._get_complete_pids.return_value = set()
    matcher.match_and_update.return_value = {"matched": 3, "updated": 1}
    return matcher


@pytest.fixture
def engine(mock_adapter, mock_matcher):
    return AnnounceEngine(adapters=[mock_adapter], matcher=mock_matcher)


# ════════════════════════════════════════════════════════════════
# check_one — L68-71
# ════════════════════════════════════════════════════════════════

class TestCheckOne:
    def test_unknown_standard_type_returns_error(self, engine):
        result = engine.check_one(standard_type="unknown")
        assert result == {"error": "未知公告类型: unknown"}

    def test_known_type_delegates_to_adapter(self, engine, mock_adapter):
        mock_adapter.fetch_announcements.return_value = [
            {"notice_date": "2024-06-01", "pid": "P001"},
            {"notice_date": "2024-07-15", "pid": "P002"},
        ]
        result = engine.check_one(standard_type="gb")

        mock_adapter.fetch_announcements.assert_called_once()
        assert result["matched"] == 3
        assert result["last_notice_date"] == "2024-07-15"


# ════════════════════════════════════════════════════════════════
# _check_one_adapter — L82-106 核心管线
# ════════════════════════════════════════════════════════════════

class TestCheckOneAdapter:
    def test_happy_path_full_pipeline(self, engine, mock_adapter, mock_matcher):
        mock_adapter.fetch_announcements.return_value = [
            {"notice_date": "2024-03-01", "pid": "P001"},
            {"notice_date": "2024-05-20", "pid": "P002"},
        ]
        result = engine._check_one_adapter(
            adapter=mock_adapter,
            since_date="2024-01-01",
            ocr_provider="baidu",
            progress_callback=None,
        )

        mock_matcher._get_complete_pids.assert_called_once_with("samr_gb")
        mock_adapter.fetch_announcements.assert_called_once()
        mock_matcher.match_and_update.assert_called_once()
        assert result["matched"] == 3
        assert result["last_notice_date"] == "2024-05-20"
        assert result["total_announcements"] == 2

    def test_fetch_exception_returns_error_dict(self, engine, mock_adapter):
        mock_adapter.fetch_announcements.side_effect = RuntimeError("网络超时")

        result = engine._check_one_adapter(
            adapter=mock_adapter,
            since_date="2024-01-01",
        )

        assert result["matched"] == 0
        assert "抓取异常" in result["error"]

    def test_empty_items_returns_fallback(self, engine, mock_adapter):
        mock_adapter.fetch_announcements.return_value = []

        result = engine._check_one_adapter(
            adapter=mock_adapter,
            since_date="2024-01-01",
        )

        assert result["matched"] == 0
        engine._matcher.match_and_update.assert_not_called()
