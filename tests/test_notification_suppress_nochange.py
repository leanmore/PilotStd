"""无变化通知静默策略。"""

from types import SimpleNamespace

from pilotstd.core.notification._dispatcher import _suppress_nochange


def _host(enabled: bool = False):
    return SimpleNamespace(_cfg={"notification.suppress_nochange": enabled})


def test_scan_empty_is_not_suppressed_by_default() -> None:
    assert _suppress_nochange(_host(), "scan_empty", {}) is False


def test_explicit_switch_can_suppress() -> None:
    assert _suppress_nochange(_host(True), "scan_empty", {}) is True


def test_announcement_zero_is_suppressed_but_failure_is_not() -> None:
    assert _suppress_nochange(_host(True), "announcement_check_complete", {"total_announcements": 0}) is True
    assert (
        _suppress_nochange(_host(True), "announcement_check_complete", {"total_announcements": 0, "failures": 1})
        is False
    )


def test_switch_off_keeps_all() -> None:
    assert _suppress_nochange(_host(False), "scan_empty", {}) is False
    assert _suppress_nochange(_host(False), "announcement_fetch_complete", {"count": 0}) is False
