"""F3：时区感知时间工具。"""

from datetime import timezone

from pilotstd.core import time_utils


def test_now_is_aware(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    dt = time_utils.now()
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 8 * 3600


def test_iso_now_has_offset(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    text = time_utils.iso_now()
    assert "T" in text
    assert text.endswith("+08:00")


def test_parse_naive_uses_local_tz(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    dt = time_utils.parse_iso("2026-11-06 14:00:00")
    assert dt.tzinfo is not None
    assert dt.isoformat() == "2026-11-06T14:00:00+08:00"


def test_to_iso_normalizes_history():
    assert time_utils.to_iso("2026-11-06 14:00:00").startswith("2026-11-06T14:00:00")
    assert time_utils.to_iso("2026-11-06T14:00:00+00:00") == "2026-11-06T14:00:00+00:00"
    assert time_utils.to_iso("") == ""


def test_invalid_tz_falls_back(monkeypatch):
    monkeypatch.setenv("TZ", "Not/AZone")
    assert time_utils.now().tzinfo is not None


def test_utc_value_preserved():
    dt = time_utils.parse_iso("2026-11-06T06:00:00Z")
    assert dt is not None
    assert dt.utcoffset() == timezone.utc.utcoffset(dt)
