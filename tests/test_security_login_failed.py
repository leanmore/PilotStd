"""第 8 批 P0 安全事件测试：security_login_failed 端到端链路。

链路：登录失败 → docker/auth.py::_notify_login_failure → 阈值判定 → 审计 +
NotificationManager.send_event("security_login_failed") → 构建器产出消息 → 渠道文本。

覆盖原则：直接驱动真实的 `_notify_login_failure`（只桩掉"失败计数"这一外部状态与
通知管理器），从而验证阈值门控、审计载荷、事件名与载荷键、以及三语渲染内容。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docker.auth import LOGIN_FAILURE_ALERT_THRESHOLD, _notify_login_failure
from pilotstd.core.notification._builders_system import _build_security_login_failed_message
from pilotstd.i18n import set_language

PAYLOAD = {
    "from_ip": "10.0.0.9",
    "failures": LOGIN_FAILURE_ALERT_THRESHOLD,
    "window_seconds": 300,
    "username": "admin",
}


def _render(message) -> str:
    """把消息摊平成可见文本，便于断言内容。"""
    parts = [message.title]
    for block in message.blocks:
        for attr in ("text", "key", "value", "label"):
            value = getattr(block, attr, None)
            if isinstance(value, str) and value:
                parts.append(value)
    return "\n".join(parts)


class TestLoginFailureAlertThreshold:
    """阈值门控：只在恰好达到阈值时告警一次，避免刷屏与压测噪声。"""

    @patch("docker.manager.get_manager")
    @patch("docker.users.count_recent_failures")
    @patch("pilotstd.core.audit.write_audit")
    def test_below_threshold_sends_nothing(self, mock_audit, mock_count, mock_get_mgr):
        mock_count.return_value = LOGIN_FAILURE_ALERT_THRESHOLD - 1
        _notify_login_failure(MagicMock(), "10.0.0.9", "admin")
        mock_audit.assert_not_called()
        mock_get_mgr.assert_not_called()

    @patch("docker.manager.get_manager")
    @patch("docker.users.count_recent_failures")
    @patch("pilotstd.core.audit.write_audit")
    def test_at_threshold_writes_audit_and_sends_event(self, mock_audit, mock_count, mock_get_mgr):
        mock_count.return_value = LOGIN_FAILURE_ALERT_THRESHOLD
        notification_mgr = MagicMock()
        mock_get_mgr.return_value = MagicMock(notification_mgr=notification_mgr)

        _notify_login_failure(MagicMock(), "10.0.0.9", "admin")

        # 审计：未认证路径，user_id 必须显式为 None（audit_logs 允许 NULL）
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["action"] == "LOGIN_FAILED"
        assert kwargs["resource"] == "POST /api/login"
        assert kwargs["user_id"] is None
        assert kwargs["detail"]["from_ip"] == "10.0.0.9"
        assert kwargs["detail"]["failures"] == LOGIN_FAILURE_ALERT_THRESHOLD
        # **审计不含密码/密钥类字段**
        assert "password" not in str(kwargs["detail"]).lower()

        # 通知：事件名与载荷键必须与构建器严格对齐
        notification_mgr.send_event.assert_called_once()
        event_name, payload = notification_mgr.send_event.call_args.args
        assert event_name == "security_login_failed"
        assert set(payload) == {"from_ip", "failures", "window_seconds", "username"}

    @patch("docker.manager.get_manager")
    @patch("docker.users.count_recent_failures")
    @patch("pilotstd.core.audit.write_audit")
    def test_above_threshold_does_not_repeat(self, mock_audit, mock_count, mock_get_mgr):
        """阈值之后继续失败不重复告警（否则攻击持续时通知刷屏）。"""
        mock_count.return_value = LOGIN_FAILURE_ALERT_THRESHOLD + 3
        _notify_login_failure(MagicMock(), "10.0.0.9", "admin")
        mock_audit.assert_not_called()
        mock_get_mgr.assert_not_called()

    @patch("docker.users.count_recent_failures")
    @patch("pilotstd.core.audit.write_audit")
    def test_notification_failure_never_breaks_login(self, mock_audit, mock_count):
        """告警链路抛异常时不得外泄（登录仍须返回 401）。"""
        mock_count.return_value = LOGIN_FAILURE_ALERT_THRESHOLD
        with patch("docker.manager.get_manager", side_effect=RuntimeError("mgr down")):
            _notify_login_failure(MagicMock(), "10.0.0.9", "admin")  # 不抛即通过

    @patch("docker.manager.get_manager")
    @patch("docker.users.count_recent_failures")
    @patch("pilotstd.core.audit.write_audit")
    def test_missing_notification_mgr_is_tolerated(self, mock_audit, mock_count, mock_get_mgr):
        """通知管理器缺失时仍写审计，不抛异常。"""
        mock_count.return_value = LOGIN_FAILURE_ALERT_THRESHOLD
        mock_get_mgr.return_value = MagicMock(notification_mgr=None)
        _notify_login_failure(MagicMock(), "10.0.0.9", "admin")
        mock_audit.assert_called_once()


class TestLoginFailureMessageRendering:
    """构建器与三语渲染（端到端：载荷 → 消息 → 渠道文本）。"""

    def test_message_contract(self):
        msg = _build_security_login_failed_message(PAYLOAD)
        assert msg.event_type == "security_login_failed"
        assert msg.level == "warning"
        assert msg.icon == "pi pi-lock"
        assert msg.blocks

    def test_renders_trilingual_and_follows_language_switch(self):
        rendered: dict[str, str] = {}
        for lang in ("zh_CN", "zh_TW", "en"):
            set_language(lang)
            rendered[lang] = _render(_build_security_login_failed_message(PAYLOAD))

        assert "登录失败告警" in rendered["zh_CN"]
        assert "登入失敗告警" in rendered["zh_TW"]
        assert "Login Failure Alert" in rendered["en"]
        # 三种语言互不相同（证明调用期取 t()，未固化语言）
        assert len({rendered["zh_CN"], rendered["zh_TW"], rendered["en"]}) == 3

    def test_payload_content_appears(self):
        set_language("zh_CN")
        text = _render(_build_security_login_failed_message(PAYLOAD))
        assert "5" in text  # 失败次数
        assert "admin" in text  # 目标账号
        assert "10.0.0.9" in text  # 来源地址

    def test_message_never_contains_password(self):
        """告警文案绝不含密码字段（构建器只读登记键，多余的密码键被忽略）。"""
        set_language("zh_CN")
        text = _render(_build_security_login_failed_message({**PAYLOAD, "password": "S3cr3t!"}))
        assert "S3cr3t!" not in text

    def test_handles_missing_optional_fields(self):
        """仅给最少字段也不崩（from_ip / username 缺失时跳过对应块）。"""
        set_language("zh_CN")
        msg = _build_security_login_failed_message({"failures": 5, "window_seconds": 300})
        assert msg.blocks
        assert "登录失败告警" in _render(msg)

    def test_window_seconds_rendered_as_minutes(self):
        set_language("zh_CN")
        text = _render(_build_security_login_failed_message({**PAYLOAD, "window_seconds": 600}))
        assert "10 分钟" in text


@pytest.fixture(autouse=True)
def _restore_language():
    """用例结束后恢复语言（与 conftest 的 i18n 隔离同源）。"""
    from pilotstd.i18n import get_language

    before = get_language()
    yield
    set_language(before)
