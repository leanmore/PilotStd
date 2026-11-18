"""同一 IP 的 Cookie 失败只通知一次（避免每小时重复）。"""
from pilotstd.wechat_ip import scheduler as s


class _Cfg:
    def __init__(self):
        self._d = {"wechat_ip.last_ip": "1.1.1.1"}
    def get(self, k, d=None): return self._d.get(k, d)
    def set(self, k, v): self._d[k] = v
    def save(self): pass


def test_same_cookie_failure_notified_once(monkeypatch):
    calls = []
    monkeypatch.setattr(s, "do_detect_ip", lambda: "2.2.2.2")
    monkeypatch.setattr(s, "_get_cookie", lambda cfg: None)
    cfg = _Cfg()
    def cb(title, body, status="info"):
        calls.append((title, body, status))
    assert s.run_check(cfg, cb)["error"] == "无法获取 Cookie"
    assert s.run_check(cfg, cb)["error"] == "无法获取 Cookie"
    assert len([c for c in calls if c[0] == "IP 更新失败"]) == 1
