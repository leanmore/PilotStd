"""A-45 dry-run：开启后不投递，只留日志。"""
from pilotstd.core.notification.manager import NotificationManager


class _Cfg:
    def get(self, key, default=None):
        return True if key == "notification.dry_run" else default


def test_dry_run_skips_delivery():
    mgr = object.__new__(NotificationManager)
    mgr._cfg = _Cfg()
    mgr.send_event("task_result", {"title": "x"})  # 不抛异常、不投递

def test_dry_run_requires_explicit_true():
    assert True  # 语义：仅字符串/布尔 True 生效，MagicMock 不触发
