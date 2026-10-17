"""安全告警：构建器缺失时的降级路径（体检 D-16）。

`security_notifier` 的 `except ImportError` 原被 `# pragma: no cover` 整段排除；
其降级语义由 `_build_security_message` 承担（构建器为 None → 记 warning、返回 None）。
本用例直接驱动该语义，证明降级路径不是"死代码"。
"""

from __future__ import annotations

import logging


def test_missing_builder_returns_none_and_warns(monkeypatch, caplog) -> None:
    from pilotstd.core.notification import security_notifier as sn

    monkeypatch.setattr(sn, "_build_security_password_changed_message", None)

    with caplog.at_level(logging.WARNING, logger="pilotstd.core.notification.security_notifier"):
        result = sn._build_security_message("security_password_changed", {"user": "u"})

    assert result is None
    assert "未登记构建器" in caplog.text


def test_unknown_event_returns_none() -> None:
    from pilotstd.core.notification import security_notifier as sn

    assert sn._build_security_message("no_such_event", {}) is None
