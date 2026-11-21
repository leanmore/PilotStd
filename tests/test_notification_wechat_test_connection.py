"""企微“应用形态”测试连接：构造参数不能错位（2026-11-21 修）。"""

from __future__ import annotations

from types import SimpleNamespace

from pilotstd.core.notification import _format_utils


class _FakeWechat:
    """记录构造入参，send 恒成功。"""

    last_init: dict | None = None

    def __init__(self, webhook_url="", corpid="", agentid="", corpsecret="", proxy_url="", touser="@all"):
        _FakeWechat.last_init = {
            "webhook_url": webhook_url,
            "corpid": corpid,
            "agentid": agentid,
            "corpsecret": corpsecret,
        }

    def send(self, message):
        return True


class _Cred:
    def get_channel(self, user_id, channel):
        return {
            "corpid": "corp-1",
            "agentid": "1000002",
            "corpsecret": "secret-1",
        }


def _mgr():
    return SimpleNamespace(_cred_helper=_Cred(), _user_id=1, _channels={})


def test_wechat_app_mode_ctor_args_aligned(monkeypatch):
    """三个值必须落在 corpid/agentid/corpsecret，而不是整体错位一位。"""
    from pilotstd.core.notification import manager as mgr_mod

    monkeypatch.setitem(mgr_mod._CHANNEL_CLASSES, "wechat", _FakeWechat)

    result = _format_utils.do_test_send(_mgr(), "wechat", message=object())

    assert result["ok"] is True, result
    assert _FakeWechat.last_init == {
        "webhook_url": "",
        "corpid": "corp-1",
        "agentid": "1000002",
        "corpsecret": "secret-1",
    }
