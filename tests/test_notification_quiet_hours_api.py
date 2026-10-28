"""A-20：全局静音时段端点（UI 配置 → 服务端 config）。

用户偏好路径与 config 路径的断链见 docs/debt/03-open.md A-20。
"""

from unittest.mock import MagicMock

from fastapi.responses import JSONResponse


def _mgr() -> MagicMock:
    mgr = MagicMock()
    mgr.cfg.set = MagicMock()
    return mgr


def _call(body: dict, mgr: MagicMock):
    from docker.api.notification_config import update_quiet_hours

    return update_quiet_hours(body, mgr=mgr)


def test_writes_three_config_keys():
    mgr = _mgr()
    result = _call({"enabled": True, "start": "23:00", "end": "06:30"}, mgr)
    assert result == {"ok": True, "enabled": True, "start": "23:00", "end": "06:30"}
    calls = {c.args[0]: c.args[1] for c in mgr.cfg.set.call_args_list}
    assert calls["notification.quiet_hours_enabled"] is True
    assert calls["notification.quiet_hours_start"] == "23:00"
    assert calls["notification.quiet_hours_end"] == "06:30"


def test_disable_writes_false():
    mgr = _mgr()
    result = _call({"enabled": False, "start": "22:00", "end": "07:00"}, mgr)
    assert result["ok"] is True
    calls = {c.args[0]: c.args[1] for c in mgr.cfg.set.call_args_list}
    assert calls["notification.quiet_hours_enabled"] is False


def test_invalid_time_rejected_without_writes():
    mgr = _mgr()
    result = _call({"enabled": True, "start": "25:00", "end": "07:00"}, mgr)
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    mgr.cfg.set.assert_not_called()
