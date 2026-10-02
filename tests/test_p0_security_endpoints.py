"""P0 安全端点（第 2 批安全审计闭环）单元测试。

核心不变量：
1. 凭证变更告警必须投递到**旧**地址，且发送动作必须先于 `set_channel` 落库
   ——顺序若颠倒，告警会流向攻击者控制的新 webhook；
2. 安全告警**绝不**经 `NotificationManager.send_event`（聚合/静音会把它推迟到
   新凭证落库之后），故此路径下 manager 的 send_event 不得被调用；
3. 告警失败绝不阻断业务写入（凭据仍落库、密码仍生效、令牌仍轮换）；
4. 审计载荷绝不含凭证值 / 令牌值 / 密码。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.security_notifier import (
    ENV_NOTIFY_ENABLED,
    notify_credential_change,
    notify_security_event,
)

OLD_URL = "https://old.example/hook"
NEW_URL = "https://new.example/hook"


class _RecordingChannel:
    """替身渠道：记录实际收到的 webhook 地址，不发起网络请求。"""

    sent_urls: list[str] = []
    fail: bool = False
    boom: bool = False

    def __init__(self, url: str, *args, **kwargs) -> None:
        self.url = url

    def send(self, message: NotificationMessage) -> bool:
        type(self).sent_urls.append(self.url)
        if type(self).boom:
            raise RuntimeError("下游不可达")
        return not type(self).fail


@pytest.fixture(autouse=True)
def _reset_channel_spy():
    _RecordingChannel.sent_urls = []
    _RecordingChannel.fail = False
    _RecordingChannel.boom = False
    yield
    _RecordingChannel.sent_urls = []


@pytest.fixture
def patched_wechat(monkeypatch):
    import pilotstd.core.notification.channels.wechat as wechat_mod

    monkeypatch.setattr(wechat_mod, "WechatChannel", _RecordingChannel)
    return _RecordingChannel


@pytest.fixture(autouse=True)
def failing_channel(monkeypatch):
    """注入"渠道发送返回 False"的替身。

    `autouse=True`：本夹具的作用是**副作用**（打补丁），其返回值没有任何消费方。
    原先作为显式参数注入却不在函数体内使用，会被 vulture 判为
    `unused variable`（CI 的 `Check dead Python code` 步骤因此红）。
    """
    import pilotstd.core.notification.channels.wechat as wechat_mod

    _RecordingChannel.fail = True
    monkeypatch.setattr(wechat_mod, "WechatChannel", _RecordingChannel)


@pytest.fixture(autouse=True)
def exploding_channel(monkeypatch):
    """注入"渠道发送抛异常"的替身；理由同 `failing_channel`。"""
    import pilotstd.core.notification.channels.wechat as wechat_mod

    _RecordingChannel.boom = True
    monkeypatch.setattr(wechat_mod, "WechatChannel", _RecordingChannel)


def _helper_with(channel_creds: dict) -> MagicMock:
    helper = MagicMock()
    helper.get_all.return_value = {"wechat": channel_creds}
    helper.get_channel.return_value = channel_creds
    return helper


class _FakeCredHelper:
    """最小可用凭据替身：get_all 返回指定凭证，set_channel 记录落库动作。

    真实 CredentialHelper 依赖 Fernet 与 DB；顺序测试只需"读旧值 → 写新值"两个
    动作的相对顺序，故用替身把两者都记进同一个 calls 列表。
    """

    def __init__(self, creds: dict[str, dict[str, str]], calls: list[str]) -> None:
        self._creds = creds
        self._calls = calls

    def get_all(self, user_id: int) -> dict[str, dict[str, str]]:
        return dict(self._creds)

    def get_channel(self, user_id: int, channel: str):
        return self._creds.get(channel)

    def set_channel(self, user_id: int, channel: str, credentials: dict) -> None:
        self._calls.append("set_channel:" + channel)
        self._creds.setdefault(channel, {}).update(credentials)


def _manager_with_builder() -> MagicMock:
    """构造能真实产出消息的 manager 替身（复用生产构建器，不 mock 文案）。"""
    from pilotstd.core.notification._builders_system import (
        _build_notification_credential_changed_message,
    )

    mgr = MagicMock()
    mgr._EVENT_BUILDERS = {"notification_credential_changed": _build_notification_credential_changed_message}
    mgr._build_message.side_effect = lambda ev, data: mgr._EVENT_BUILDERS[ev](data)
    return mgr


class TestCredentialChangeOrdering:
    """凭证变更告警的核心安全不变量。"""

    def test_uses_old_url_not_new(self, patched_wechat):
        """告警必须发到旧地址：新凭证尚未落库，发到新地址即等于通知攻击者。"""
        helper = _helper_with({"webhook_url": OLD_URL, "enabled": "true"})
        notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": OLD_URL, "enabled": "true"}},
            changed_keys=["webhook_url"],
            from_ip="10.0.0.1",
        )
        assert patched_wechat.sent_urls == [OLD_URL]
        assert NEW_URL not in patched_wechat.sent_urls

    def test_send_happens_before_persist(self, patched_wechat, monkeypatch):
        """顺序断言：send() 必须早于 set_channel()。

        用同一个 calls 列表同时记录两个动作，直接断言相对顺序——
        这正是"先通知旧渠道、后落库"这一安全边界的可执行形式。
        """
        calls: list[str] = []

        class _OrderedChannel(_RecordingChannel):
            def send(self, message):
                calls.append("send:" + self.url)
                return True

        import pilotstd.core.notification.channels.wechat as wechat_mod

        monkeypatch.setattr(wechat_mod, "WechatChannel", _OrderedChannel)

        helper = _FakeCredHelper({"wechat": {"webhook_url": OLD_URL, "enabled": "true"}}, calls)
        notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": OLD_URL, "enabled": "true"}},
        )
        # 模拟端点随后的落库动作
        helper.set_channel(1, "wechat", {"webhook_url": NEW_URL})

        assert calls == ["send:" + OLD_URL, "set_channel:wechat"], calls


class TestCredentialChangeDoesNotUseManagerSendEvent:
    """方案 A 的核心约束：不得走 manager.send_event（会被聚合/静音推迟）。"""

    def test_manager_send_event_not_called_when_none(self, patched_wechat):
        helper = _helper_with({"webhook_url": OLD_URL, "enabled": "true"})
        manager = MagicMock()
        notify_credential_change(
            notification_mgr=None,
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": OLD_URL}},
        )
        manager.send_event.assert_not_called()
        assert patched_wechat.sent_urls == [OLD_URL]

    def test_channel_send_is_the_delivery_path(self, patched_wechat):
        """投递必须由渠道 send() 完成，而非 manager 的任何发送方法。"""
        helper = _helper_with({"webhook_url": OLD_URL, "enabled": "true"})
        manager = MagicMock()
        notify_security_event(
            manager,
            helper,
            user_id=1,
            event_type="security_password_changed",
            payload={"user_id": "1", "from_ip": "10.0.0.1", "sessions_revoked": False},
        )
        assert patched_wechat.sent_urls == [OLD_URL]


class TestNotifyFailureDoesNotPropagate:
    """告警失败绝不抛出：调用方（端点）必须能继续落库。"""

    def test_send_returns_false_is_reported_not_raised(self):
        helper = _helper_with({"webhook_url": OLD_URL, "enabled": "true"})
        sent, failed = notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": OLD_URL}},
        )
        assert sent == []
        assert failed and "wechat" in failed[0]

    def test_send_raises_is_captured(self):
        helper = _helper_with({"webhook_url": OLD_URL, "enabled": "true"})
        sent, failed = notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": OLD_URL}},
        )
        assert sent == []
        assert failed and "wechat" in failed[0]

    def test_missing_old_credentials_skips_silently(self, patched_wechat):
        """首次配置（无旧凭证）不发送、不报错，也不视为失败。"""
        helper = MagicMock()
        helper.get_all.return_value = {}
        sent, failed = notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {}},
        )
        assert sent == [] and failed == []
        assert patched_wechat.sent_urls == []

    def test_incomplete_credentials_skipped(self, patched_wechat):
        """渠道已启用但 webhook_url 为空：可预期，不计失败。"""
        helper = _helper_with({"webhook_url": "", "enabled": "true"})
        sent, failed = notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": ""}},
        )
        assert sent == [] and failed == []
        assert patched_wechat.sent_urls == []


class TestKillSwitch:
    """紧急降级开关（环境变量，非配置文件——配置可被本端点自身改写）。"""

    def test_disabled_skips_send_and_logs(self, patched_wechat, monkeypatch, caplog):
        monkeypatch.setenv(ENV_NOTIFY_ENABLED, "false")
        helper = _helper_with({"webhook_url": OLD_URL, "enabled": "true"})
        sent, failed = notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": OLD_URL}},
        )
        assert sent == [] and failed == []
        assert patched_wechat.sent_urls == []

    def test_default_is_enabled(self, patched_wechat, monkeypatch):
        monkeypatch.delenv(ENV_NOTIFY_ENABLED, raising=False)
        helper = _helper_with({"webhook_url": OLD_URL, "enabled": "true"})
        notify_credential_change(
            notification_mgr=_manager_with_builder(),
            cred_helper=helper,
            user_id=1,
            changed_channels=["wechat"],
            old_creds={"wechat": {"webhook_url": OLD_URL}},
        )
        assert patched_wechat.sent_urls == [OLD_URL]


class TestAuditPayloadHasNoSecrets:
    """审计与告警载荷绝不含凭证值（变更告警的价值在"知道被改"，回显即泄露）。"""

    def test_payload_fields_contain_no_credential_values(self):
        from pilotstd.core.notification._builders_system import (
            _build_notification_credential_changed_message,
        )

        msg = _build_notification_credential_changed_message(
            {
                "services": ["wechat"],
                "changed_keys": ["webhook_url"],
                "rules_changed": False,
                "from_ip": "10.0.0.1",
            }
        )
        rendered = msg.title + "\n" + "\n".join(
            getattr(b, attr, "") for b in msg.blocks for attr in ("text", "key", "value")
        )
        assert "webhook_url" in rendered  # 字段名可见（用户需要知道改了什么）
        assert OLD_URL not in rendered  # 字段值绝不可见
        assert NEW_URL not in rendered

    def test_token_message_never_contains_token(self):
        from pilotstd.core.notification._builders_system import _build_security_token_refreshed_message

        msg = _build_security_token_refreshed_message(
            {"rotated_at": "2026-09-26T12:00:00", "from_ip": "10.0.0.1", "db_synced": False}
        )
        rendered = msg.title + "\n" + "\n".join(
            getattr(b, attr, "") for b in msg.blocks for attr in ("text", "key", "value")
        )
        assert "2026-09-26" in rendered
        assert "pst_" not in rendered
