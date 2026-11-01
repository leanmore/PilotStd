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
        lambda host, event, data, bypass, targets, ctx: captured.setdefault("ctx", ctx),
    )
    mgr = object.__new__(NotificationManager)
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
