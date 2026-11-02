"""A 组契约：渠道可清空字段与敏感字段的掩码/差异语义。"""

from docker.api.notification_config import _diff_credential_changes
from pilotstd.core.notification.channel_spec import CHANNEL_SPECS


class _Cred:
    MASKED_VALUES = {"***"}

    def __init__(self, old):
        self._old = old

    def get_channel(self, user_id, channel):
        return self._old


def _by_name():
    return {s.name: {f.name: f for f in s.fields} for s in CHANNEL_SPECS}


def test_webhook_urls_are_not_masked_and_token_is_masked():
    fields = _by_name()
    for name in ("wechat", "dingtalk", "feishu"):
        assert fields[name]["webhook_url"].mask is False
    assert fields["wechat"]["token"].mask is True
    assert fields["wechat"]["token"].type == "text_password"


def test_clearable_empty_is_a_change():
    cred = _Cred({"proxy_url": "https://qyapi.weixin.qq.com/"})
    _, _, channels, keys = _diff_credential_changes(
        {"channels": {"wechat": {"proxy_url": ""}}}, cred, 1
    )
    assert channels == ["wechat"]
    assert keys == ["proxy_url"]


def test_sensitive_empty_is_still_ignored():
    cred = _Cred({"corpsecret": "REAL"})
    _, _, channels, keys = _diff_credential_changes(
        {"channels": {"wechat": {"corpsecret": ""}}}, cred, 1
    )
    assert channels == []
    assert keys == []


def test_unchanged_clearable_empty_is_ignored():
    cred = _Cred({})
    _, _, channels, keys = _diff_credential_changes(
        {"channels": {"wechat": {"proxy_url": ""}}}, cred, 1
    )
    assert channels == []
    assert keys == []
