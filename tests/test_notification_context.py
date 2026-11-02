"""A-21 第三步 3a：NotificationContext 语义。"""

import pytest

from pilotstd.core.notification.context import NotificationContext


def test_user_requires_user_id():
    with pytest.raises(ValueError):
        NotificationContext(scope="user")
    assert NotificationContext(scope="user", user_id=2).log_user_id == 2


def test_admin_requires_real_user_id():
    with pytest.raises(ValueError):
        NotificationContext(scope="admin")
    assert NotificationContext(scope="admin", user_id=1).log_user_id == 1


def test_system_logs_zero():
    assert NotificationContext(scope="system").log_user_id == 0


def test_system_rejects_user_id():
    with pytest.raises(ValueError):
        NotificationContext(scope="system", user_id=1)


def test_send_event_defaults_to_system_zero(monkeypatch):
    """旧调用不传 context：默认 system，落库 0（3a 行为）。"""
    from pilotstd.core.notification import _dispatcher
    from pilotstd.core.notification.manager import NotificationManager

    captured = {}
    monkeypatch.setattr(
        _dispatcher,
        "send_event",
        lambda host, event, data, bypass, targets, ctx, **kw: captured.setdefault("ctx", ctx),
    )
    mgr = object.__new__(NotificationManager)
    mgr._user_id = 1
    NotificationManager.send_event(mgr, "scan_complete", {})
    assert captured["ctx"].scope == "system"
    assert captured["ctx"].log_user_id == 0


def test_favorites_entry_wires_user_context():
    """3b-1：收藏入口必须显式传 user context（防回退 system）。"""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "docker" / "api" / "favorites.py"
    ).read_text(encoding="utf-8")
    assert 'NotificationContext(scope="user", user_id=user_id)' in source
def test_notify_favorite_created_sends_once_with_user_context():
    """3b-1 盲区：收藏成功后必须真的调用 send_event 一次，且带 user context。"""
    from unittest.mock import MagicMock

    from docker.api.favorites import _notify_favorite_created

    mgr = MagicMock()
    payload = {"user_id": 3, "record_id": 1}
    _notify_favorite_created(mgr, 3, payload)
    mgr.notification_mgr.send_event.assert_called_once()
    event, data = mgr.notification_mgr.send_event.call_args.args
    ctx = mgr.notification_mgr.send_event.call_args.kwargs["context"]
    assert event == "favorite_created"
    assert data == payload
    assert ctx.scope == "user"
    assert ctx.user_id == 3
def test_notify_favorite_created_without_manager_is_safe():
    """manager/notification_mgr 缺失时只告警，不抛异常、不调用 send_event。"""
    from unittest.mock import MagicMock

    from docker.api.favorites import _notify_favorite_created

    mgr = MagicMock()
    mgr.notification_mgr = None
    _notify_favorite_created(mgr, 3, {"user_id": 3})  # 不抛异常即通过
