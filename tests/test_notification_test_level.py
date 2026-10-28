"""N1 验收支撑：/api/notification/test 的 level 白名单（仅 info/warning）。"""

from unittest.mock import MagicMock

import docker.api.notification as notif_api


def _mgr() -> MagicMock:
    mgr = MagicMock()
    mgr.test_send.return_value = {"ok": True}
    return mgr


def test_default_level_is_info():
    mgr = _mgr()
    result = notif_api.test_notification(None, {"channel": "telegram"}, nmgr=mgr)
    assert result == {"ok": True}
    msg = mgr.test_send.call_args.args[1]
    assert msg.level == "info"


def test_warning_level_accepted():
    mgr = _mgr()
    result = notif_api.test_notification(None, {"channel": "telegram", "level": "warning"}, nmgr=mgr)
    assert result == {"ok": True}
    msg = mgr.test_send.call_args.args[1]
    assert msg.level == "warning"


def test_other_levels_rejected():
    mgr = _mgr()
    for level in ("error", "critical", "debug", ""):
        body = {"channel": "telegram", "level": level} if level else {"channel": "telegram"}
        result = notif_api.test_notification(None, body, nmgr=mgr)
        if level == "":
            # 空字符串走默认 info，仍允许
            assert result == {"ok": True}
        else:
            assert result["ok"] is False
            assert "unsupported level" in result["error"]
    assert mgr.test_send.call_count == 1
