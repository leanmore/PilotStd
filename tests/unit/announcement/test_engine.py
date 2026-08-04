"""engine.py 单元测试 — AnnounceEngine 并发编排全覆盖。

跳过: adapters/samr_*.py（纯配置模板）、base.py 日志/统计缺口（ROI 低）
"""

import concurrent.futures
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.announcement.engine import AnnounceEngine


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.standard_type = "gb"
    adapter.source_site = "samr_gb"
    adapter.fetch_announcements.return_value = [
        {"notice_date": "2025-06-01", "title": "公告1"},
        {"notice_date": "2025-06-15", "title": "公告2"},
    ]
    return adapter


@pytest.fixture
def mock_matcher():
    matcher = MagicMock()
    matcher._get_complete_pids.return_value = set()
    matcher.match_and_update.return_value = {"matched": 2, "updated": 1}
    return matcher


@pytest.fixture
def engine(mock_adapter, mock_matcher):
    return AnnounceEngine(adapters=[mock_adapter], matcher=mock_matcher)


# ════════════════════════════════════════════════════════════
# check_one + _check_one_adapter
# ════════════════════════════════════════════════════════════

class TestCheckOne:
    def test_nonexistent_type_returns_error(self, engine):
        result = engine.check_one("unknown_type")
        assert "error" in result
        assert "未知公告类型" in result["error"]

    def test_happy_path_returns_stats(self, engine, mock_adapter, mock_matcher):
        result = engine.check_one("gb")
        assert result["matched"] == 2
        assert result["updated"] == 1
        assert result["total_announcements"] == 2
        assert result["last_notice_date"] == "2025-06-15"

    def test_adapter_fetch_exception_returns_default(self, engine, mock_adapter):
        mock_adapter.fetch_announcements.side_effect = RuntimeError("fetch boom")
        result = engine.check_one("gb")
        assert result["matched"] == 0
        assert result["updated"] == 0
        assert "抓取异常" in result.get("error", "")

    def test_empty_items_returns_zero_stats(self, engine, mock_adapter):
        mock_adapter.fetch_announcements.return_value = []
        result = engine.check_one("gb")
        assert result["matched"] == 0
        assert result["updated"] == 0
        assert result["total_announcements"] == 0

    def test_max_date_picks_latest(self, engine, mock_adapter):
        mock_adapter.fetch_announcements.return_value = [
            {"notice_date": "2025-01-01"},
            {"notice_date": "2025-12-31"},
            {"notice_date": "2025-06-15"},
        ]
        result = engine.check_one("gb")
        assert result["last_notice_date"] == "2025-12-31"

    def test_max_date_missing_key_skipped(self, engine, mock_adapter):
        """部分条目无 notice_date → 跳过，取其他条目最大值。"""
        mock_adapter.fetch_announcements.return_value = [
            {"notice_date": "2025-03-01"},
            {"title": "no date"},
        ]
        result = engine.check_one("gb")
        assert result["last_notice_date"] == "2025-03-01"

    def test_all_progress_callback_passed(self, engine, mock_adapter):
        progress = MagicMock()
        engine.check_one("gb", progress_callback=progress)
        call_kwargs = mock_adapter.fetch_announcements.call_args[1]
        assert call_kwargs["progress_callback"] is progress


# ════════════════════════════════════════════════════════════
# check_all — 并发编排 + 异常兜底
# ════════════════════════════════════════════════════════════

class TestCheckAll:
    @pytest.fixture
    def gb_adapter(self):
        a = MagicMock()
        a.standard_type = "gb"
        a.source_site = "samr_gb"
        a.fetch_announcements.return_value = [{"notice_date": "2025-06-01"}]
        return a

    @pytest.fixture
    def hb_adapter(self):
        a = MagicMock()
        a.standard_type = "hb"
        a.source_site = "samr_hb"
        a.fetch_announcements.return_value = [{"notice_date": "2025-07-01"}]
        return a

    @pytest.fixture
    def db_adapter(self):
        a = MagicMock()
        a.standard_type = "db"
        a.source_site = "samr_db"
        a.fetch_announcements.return_value = [{"notice_date": "2025-08-01"}]
        return a

    def test_all_three_succeed(self, gb_adapter, hb_adapter, db_adapter):
        matcher = MagicMock()
        matcher._get_complete_pids.return_value = set()
        matcher.match_and_update.return_value = {"matched": 1, "updated": 1}

        engine = AnnounceEngine([gb_adapter, hb_adapter, db_adapter], matcher)
        result = engine.check_all()

        assert "gb" in result
        assert "hb" in result
        assert "db" in result
        assert result["gb"]["updated"] == 1

    def test_one_adapter_fails_others_succeed(self, gb_adapter, hb_adapter):
        """gb 异常，hb 正常 — 单点故障不影响其他。"""
        gb_adapter.fetch_announcements.side_effect = RuntimeError("gb down")

        matcher = MagicMock()
        matcher._get_complete_pids.return_value = set()
        matcher.match_and_update.return_value = {"matched": 1, "updated": 1}

        engine = AnnounceEngine([gb_adapter, hb_adapter], matcher)
        result = engine.check_all()

        assert "error" in result["gb"]
        assert result["gb"]["matched"] == 0
        assert result["hb"]["matched"] == 1  # hb 正常

    def test_missing_adapter_type_skipped(self, gb_adapter):
        """只有 gb 适配器时，hb/db 不在结果中。"""
        matcher = MagicMock()
        matcher._get_complete_pids.return_value = set()
        matcher.match_and_update.return_value = {"matched": 1, "updated": 1}

        engine = AnnounceEngine([gb_adapter], matcher)
        result = engine.check_all()

        assert "gb" in result
        assert "hb" not in result
        assert "db" not in result

    def test_all_adapters_fail(self, gb_adapter, hb_adapter, db_adapter):
        """全部异常 → 所有结果都有 error 字段。"""
        gb_adapter.fetch_announcements.side_effect = RuntimeError("boom")
        hb_adapter.fetch_announcements.side_effect = RuntimeError("boom")
        db_adapter.fetch_announcements.side_effect = RuntimeError("boom")

        matcher = MagicMock()
        matcher._get_complete_pids.return_value = set()

        engine = AnnounceEngine([gb_adapter, hb_adapter, db_adapter], matcher)
        result = engine.check_all()

        assert all("error" in str(v) for v in result.values())

    def test_ocr_provider_passed_to_adapter(self, gb_adapter):
        """ocr_provider → 透传到 adapter.fetch_announcements。"""
        matcher = MagicMock()
        matcher._get_complete_pids.return_value = set()
        matcher.match_and_update.return_value = {"matched": 0, "updated": 0}

        mock_ocr = MagicMock()
        engine = AnnounceEngine([gb_adapter], matcher)
        engine.check_all(ocr_provider=mock_ocr)

        call_kwargs = gb_adapter.fetch_announcements.call_args[1]
        assert call_kwargs["ocr_provider"] is mock_ocr

    def test_adapters_property_returns_list(self, gb_adapter):
        engine = AnnounceEngine([gb_adapter], MagicMock())
        assert len(engine.adapters) == 1
