"""阶段 D（可见性解耦）：关闭投递仍写库日志，但不调用渠道 send()。

设计依据：[03-impl-design-D.md](../../docs/plans/notification-system-design/03-impl-design-D.md) §1.2 D 行
（目标"关闭推送时仍写 `notification_log`"；验收"关闭投递→有日志且渠道 `send()` 未被调用；
启用→与现状逐项一致"；回滚 `NOTIFY_RECORD_WHEN_DISABLED=v0`）。
"""

from pilotstd.core.notification._dispatcher import send_event
from pilotstd.core.notification.channel import NotificationMessage


class _Policy:
    def __init__(self, channels):
        self._channels = channels

    def get_channels_for_event(self, user_id, event_type):  # noqa: ARG002 - 契约签名
        return list(self._channels)


class _Channel:
    def __init__(self):
        self.sent = 0

    def send(self, message):  # noqa: ARG002 - 契约签名
        self.sent += 1
        return True


class _Host:
    """最小管理器替身：只暴露 `send_event` 用到的成员。"""

    def __init__(self, enabled: bool, channels=("telegram",)):
        self._enabled = enabled
        self._user_id = 1
        self._local_sink = None  # W2 分流出口：本用例不注入（等价于 Docker 端）
        self._policy = _Policy(channels)
        self.logs: list[tuple] = []
        self.channel = _Channel()
        self._channels = {"telegram": self.channel}

    def _build_message(self, event_type, data):
        return NotificationMessage(title="标题", body="正文", event_type=event_type)

    def _log(self, event_type, channel, msg, status, error_msg, sent_at):
        self.logs.append((event_type, channel, status, error_msg))

    def _validate_message(self, msg, event_type):
        return None


def test_disabled_writes_skipped_log_without_send(monkeypatch):
    """关闭投递（默认口径）：写 status=skipped 的日志行，且渠道 send() 一次都没被调用。"""
    monkeypatch.delenv("NOTIFY_RECORD_WHEN_DISABLED", raising=False)
    host = _Host(enabled=False)
    send_event(host, "scan_complete", {"total": 3})

    assert host.channel.sent == 0, "关闭投递时不得调用渠道 send()"
    assert len(host.logs) == 1
    event_type, channel, status, reason = host.logs[0]
    assert (event_type, channel, status) == ("scan_complete", "telegram", "skipped")
    assert reason  # 原因非空（i18n 文案），供 Web 端解释


def test_disabled_rollback_flag_restores_old_behaviour(monkeypatch):
    """回滚开关：NOTIFY_RECORD_WHEN_DISABLED=v0 ⇒ 回到"关闭即不写日志"。"""
    monkeypatch.setenv("NOTIFY_RECORD_WHEN_DISABLED", "v0")
    host = _Host(enabled=False)
    send_event(host, "scan_complete", {"total": 3})

    assert host.logs == []
    assert host.channel.sent == 0


def test_disabled_without_subscribers_writes_nothing(monkeypatch):
    """没有任何订阅渠道时不写行（避免"没有收件人"的噪声行）。"""
    monkeypatch.delenv("NOTIFY_RECORD_WHEN_DISABLED", raising=False)
    host = _Host(enabled=False, channels=())
    send_event(host, "scan_complete", {"total": 3})
    assert host.logs == []


def test_enabled_path_never_writes_skipped(monkeypatch):
    """启用投递时不会出现 skipped 行（该状态专属于"关闭投递但记录"）。

    启用路径的逐项行为由既有链路用例覆盖（tests/test_notification_manager.py 等），
    本用例只锁"阶段 D 不改变启用路径的日志语义"。
    """
    monkeypatch.delenv("NOTIFY_RECORD_WHEN_DISABLED", raising=False)
    host = _Host(enabled=True, channels=())  # 无订阅 ⇒ 走既有"无渠道"分支，不落 skipped
    send_event(host, "scan_complete", {"total": 3})

    assert host.channel.sent == 0
    assert all(row[2] != "skipped" for row in host.logs)
