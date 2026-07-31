"""core/notification/_format_utils.py 补测。"""
from unittest.mock import MagicMock
import pytest
from pilotstd.core.notification._format_utils import format_standard_status_changed_aggregated


def _make_entry(num, new_status="现行", old_status="现行"):
    msg = MagicMock()
    msg.standard_number = f"GB/T {num}"
    msg.standard_name = f"标准{num}"
    msg.new_status = new_status
    msg.old_status = old_status
    msg.changed_at = "2026-01-15T10:30:00+08:00"
    return (msg, "channel", "2026-01-15")


class TestFormatAggregated:
    def test_single_entry(self):
        entries = [_make_entry(1)]
        result = format_standard_status_changed_aggregated("", entries, 1)
        assert "GB/T 1" in result
        assert "标准1" in result

    def test_expired_count_in_header(self):
        entries = [_make_entry(1, new_status="废止")]
        result = format_standard_status_changed_aggregated("", entries, 1)
        assert "废止" in result

    def test_multiple_entries_under_10(self):
        entries = [_make_entry(i) for i in range(5)]
        result = format_standard_status_changed_aggregated("", entries, 5)
        assert "5 项" in result

    def test_over_10_entries_truncated(self):
        entries = [_make_entry(i) for i in range(15)]
        result = format_standard_status_changed_aggregated("", entries, 15)
        assert "等 5 项" in result

        msg.standard_name = "Y"
        msg.new_status = "现行"
        msg.old_status = "现行"
        msg.changed_at = ""
        entries = [(msg, "ch", "ts")]
        result = format_standard_status_changed_aggregated("", entries, 1)
        assert "X" in result

    def test_expired_in_overflow_range(self):
        entries = [_make_entry(i, new_status="废止" if i >= 10 else "现行") for i in range(12)]
        result = format_standard_status_changed_aggregated("", entries, 12)
        assert "废止" in result
