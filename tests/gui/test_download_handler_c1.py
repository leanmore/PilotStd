# tests/gui/test_download_handler_c1.py
"""DownloadUIHandler Phase 3 C1 集成测试 — 纯 Python，不启动 QApplication。

验证 3 个新增公开接口正确委托给 DownloadFlowEngine。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilotstd.ui.core.handlers._download import DownloadUIHandler


def _make_mock_config():
    config = MagicMock()
    config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "download.min_file_size": 100,
            "download.max_file_size": 10000,
        }.get(key, default)
    )
    return config


def _make_handler(**overrides):
    kwargs = dict(
        mgr=MagicMock(),
        config=_make_mock_config(),
        pause_event=MagicMock(),
        parent_widget=None,
        work_table=MagicMock(),
        status_callback=MagicMock(),
        progress_callback=MagicMock(),
        show_stage_dialog=MagicMock(),
        question_dlg=MagicMock(),
        stage_prereq_dialog=MagicMock(),
        register_task=MagicMock(),
        project_mark_dirty=MagicMock(),
        suppress_dialogs=MagicMock(return_value=False),
        add_table_row=MagicMock(),
        find_row_by_seq=MagicMock(return_value=-1),
    )
    kwargs.update(overrides)
    return DownloadUIHandler(**kwargs)


@pytest.fixture
def handler():
    return _make_handler()


class TestValidateDownloadUrl:
    def test_valid_url(self, handler):
        result = handler.validate_download_url("https://example.com/file.zip")
        assert result["valid"] is True
        assert result["scheme"] == "https"

    def test_invalid_url(self, handler):
        result = handler.validate_download_url("not-a-url")
        assert result["valid"] is False


class TestGetRetryDelay:
    def test_returns_expected_value(self, handler):
        delay = handler.get_retry_delay(2)
        assert delay > 0
        assert isinstance(delay, float)

    def test_zero_attempt(self, handler):
        assert handler.get_retry_delay(0) >= 1.0


class TestCheckFileSizeCompliance:
    def test_within_limits(self, handler):
        result = handler.check_file_size_compliance(500)
        assert result["valid"] is True

    def test_below_min(self, handler):
        result = handler.check_file_size_compliance(50)
        assert result["valid"] is False
        assert "过小" in result["message"]

    def test_above_max(self, handler):
        result = handler.check_file_size_compliance(20000)
        assert result["valid"] is False
        assert "过大" in result["message"]
