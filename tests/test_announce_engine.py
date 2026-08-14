"""announcement/engine.py 补测。"""
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.announcement.engine import AnnounceEngine


@pytest.fixture
def engine():
    gb = MagicMock()
    gb.standard_type = "gb"
    hb = MagicMock()
    hb.standard_type = "hb"
    db = MagicMock()
    db.standard_type = "db"
    matcher = MagicMock()
    return AnnounceEngine(adapters=[gb, hb, db], matcher=matcher)


class TestAnnounceEngine:
    def test_adapters_property(self, engine):
        assert len(engine.adapters) == 3

    def test_check_all_empty(self, engine):
        engine._adapters = {}
        r = engine.check_all()
        assert r == {}

    def test_check_all_with_mock_executor(self, engine):
        mock_future = MagicMock()
        mock_future.result.return_value = {"matched": 5, "updated": 3,
                                             "total_announcements": 10, "last_notice_date": "2026-01-01"}
        with patch("concurrent.futures.ThreadPoolExecutor") as MockExec:
            MockExec.return_value.__enter__.return_value.submit.return_value = mock_future
            with patch("concurrent.futures.as_completed", return_value=[mock_future]):
                r = engine.check_all(since_date="2026-01-01")
                assert len(r) >= 1

    def test_check_one_adapter_exception_fallback(self, engine):
        """单适配器异常被捕获。"""
        with patch.object(engine, "_check_one_adapter", side_effect=Exception("fail")):
            engine._adapters = {"gb": MagicMock()}
            with patch("concurrent.futures.ThreadPoolExecutor") as MockExec:
                mock_future = MagicMock()
                MockExec.return_value.__enter__.return_value.submit.return_value = mock_future
                with patch("concurrent.futures.as_completed", return_value=[mock_future]):
                    mock_future.result.side_effect = Exception("boom")
                    r = engine.check_all()
                    assert len(r) >= 1
                    assert r["gb"]["matched"] == 0  # 默认兜底值
