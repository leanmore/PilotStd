# tests/unit/test_settings_event_handlers.py
"""Pure-function tests for settings event handler logic.

sanitize_setting_value 由 _on_announce_url_changed / _on_announce_api_key_changed 共用，
负责清洗用户输入的文本值。
"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers._settings import sanitize_setting_value


class TestSanitizeSettingValue:
    def test_strips_leading_whitespace(self):
        assert sanitize_setting_value("  https://example.com") == "https://example.com"

    def test_strips_trailing_whitespace(self):
        assert sanitize_setting_value("https://example.com  ") == "https://example.com"

    def test_strips_both_sides(self):
        assert sanitize_setting_value("  https://example.com  ") == "https://example.com"

    def test_empty_string_returns_empty(self):
        assert sanitize_setting_value("") == ""

    def test_whitespace_only_returns_empty(self):
        assert sanitize_setting_value("   \t\n  ") == ""

    def test_preserves_internal_spaces(self):
        assert sanitize_setting_value("  hello world  ") == "hello world"

    def test_no_change_for_clean_value(self):
        assert sanitize_setting_value("clean") == "clean"
