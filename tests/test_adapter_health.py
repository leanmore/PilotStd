"""F1：适配器连续 0 条检测与验证码退避。"""

from types import SimpleNamespace

from pilotstd.query.rotator import SiteRotator, SiteState


def test_consecutive_empty_marks_suspected(monkeypatch):
    calls = []
    monkeypatch.setattr("pilotstd.core.notification.notify_system", lambda event, data: calls.append((event, data)))
    r = SiteRotator([SiteState(name="site_a", base_url="https://a.example")])
    for _ in range(9):
        r.record_result("site_a", found=False)
    assert r.get_cooldown_remaining("site_a") == 0
    r.record_result("site_a", found=False)
    assert r.get_cooldown_remaining("site_a") > 0
    assert calls and calls[0][0] == "adapter_suspected_failure"
    assert calls[0][1]["adapter"] == "site_a"


def test_found_resets_empty_streak(monkeypatch):
    monkeypatch.setattr("pilotstd.core.notification.notify_system", lambda *a: None)
    r = SiteRotator([SiteState(name="site_b", base_url="https://b.example")])
    for _ in range(9):
        r.record_result("site_b", found=False)
    r.record_result("site_b", found=True)
    r.record_result("site_b", found=False)
    assert r.get_cooldown_remaining("site_b") == 0


def test_captcha_backoff_increases_and_resets(monkeypatch):
    from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter

    notified = []
    monkeypatch.setattr("pilotstd.core.notification.notify_system", lambda e, d: notified.append(e))
    adapter = OpenstdDownloadAdapter()
    task = SimpleNamespace(standard_number="GB/T 1-2020")
    adapter._register_captcha_failure(task)
    first = adapter._captcha_cooldown_until
    adapter._register_captcha_failure(task)
    assert adapter._captcha_fail_streak == 2
    assert adapter._captcha_cooldown_until > first
    assert notified == ["captcha_backoff", "captcha_backoff"]
