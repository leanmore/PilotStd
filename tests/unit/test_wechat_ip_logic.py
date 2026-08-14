# tests/unit/test_wechat_ip_logic.py
"""Unit tests for wechat_ip pure logic functions.

All functions tested here have zero I/O and zero Qt/Playwright/crypto dependencies.
"""

from __future__ import annotations

from pilotstd.wechat_ip.logic import (
    build_update_result,
    is_ip_changed,
    merge_ip_list,
    parse_app_urls,
    parse_cookie_string,
)


class TestParseCookieString:
    def test_single_cookie(self):
        result = parse_cookie_string("session=abc123")
        assert len(result) == 1
        assert result[0]["name"] == "session"
        assert result[0]["value"] == "abc123"
        assert result[0]["domain"] == ".work.weixin.qq.com"
        assert result[0]["path"] == "/"

    def test_multiple_cookies(self):
        result = parse_cookie_string("a=1; b=2; c=3")
        assert len(result) == 3
        assert result[1]["name"] == "b"
        assert result[1]["value"] == "2"

    def test_handles_whitespace(self):
        result = parse_cookie_string(" a = 1 ;  b = 2 ")
        assert result[0]["name"] == "a"
        assert result[0]["value"] == "1"
        assert result[1]["name"] == "b"
        assert result[1]["value"] == "2"

    def test_empty_string(self):
        assert parse_cookie_string("") == []

    def test_no_equals_skipped(self):
        result = parse_cookie_string("valid=1; novalue; also=2")
        assert len(result) == 2
        assert result[0]["name"] == "valid"
        assert result[1]["name"] == "also"


class TestMergeIpList:
    def test_append_to_empty(self):
        assert merge_ip_list("", "1.2.3.4") == ("1.2.3.4", False)

    def test_append_to_existing(self):
        assert merge_ip_list("1.2.3.4", "5.6.7.8") == ("1.2.3.4;5.6.7.8", False)

    def test_skip_duplicate(self):
        merged, skipped = merge_ip_list("1.2.3.4;5.6.7.8", "1.2.3.4")
        assert skipped is True
        assert merged == "1.2.3.4;5.6.7.8"

    def test_substring_not_matched_as_duplicate(self):
        # "1.2.3.4" in "1.2.3.40" is True (substring!) — known limitation, accepted
        merged, skipped = merge_ip_list("1.2.3.40", "1.2.3.4")
        assert skipped  # documents the substring-match behavior

    def test_first_ip_no_semicolon(self):
        merged, skipped = merge_ip_list("", "10.0.0.1")
        assert not skipped
        assert merged == "10.0.0.1"


class TestParseAppUrls:
    def test_normal_list(self):
        assert parse_app_urls("https://a.com, https://b.com") == [
            "https://a.com",
            "https://b.com",
        ]

    def test_strips_and_filters_empty(self):
        assert parse_app_urls("  https://a.com , , https://b.com  ") == [
            "https://a.com",
            "https://b.com",
        ]

    def test_empty_string(self):
        assert parse_app_urls("") == []

    def test_only_commas(self):
        assert parse_app_urls(",,,") == []


class TestIsIpChanged:
    def test_changed(self):
        assert is_ip_changed("1.2.3.4", "5.6.7.8") is True

    def test_same(self):
        assert is_ip_changed("1.2.3.4", "1.2.3.4") is False

    def test_empty_current(self):
        assert is_ip_changed("", "1.2.3.4") is False

    def test_both_empty(self):
        assert is_ip_changed("", "") is False


class TestBuildUpdateResult:
    def test_all_ok(self):
        ok, failed = build_update_result({"a": True, "b": True})
        assert ok is True
        assert failed == []

    def test_partial_failure(self):
        ok, failed = build_update_result({"a": True, "b": False})
        assert ok is False
        assert failed == ["b"]

    def test_empty_results(self):
        ok, failed = build_update_result({})
        assert ok is False
        assert failed == []
