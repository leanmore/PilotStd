"""D-2 阶段 1 缺口①：无策略/无规则时回退“已启用渠道”。"""

from __future__ import annotations

from typing import Any

import pytest

from pilotstd.core.notification._policy import NotificationPolicyHelper


class _FakeDB:
    """策略表为空（新装用户）的替身。"""

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return []

    def fetchone(self, sql: str, params: tuple = ()) -> None:
        return None

    def execute(self, sql: str, params: tuple = ()) -> None:
        return None


class _Cfg:
    """按 key 返回配置；用于模拟“哪些渠道已启用”。"""

    def __init__(self, enabled: dict[str, bool] | None = None, rules: dict[str, Any] | None = None) -> None:
        self._enabled = enabled or {}
        self._rules = rules or {}

    def get(self, key: str) -> Any:
        if key.startswith("notification.channels.") and key.endswith(".enabled"):
            return self._enabled.get(key.split(".")[2], False)
        if key.startswith("notification.rules."):
            return self._rules.get(key.split(".", 2)[2])
        return None


@pytest.mark.parametrize(
    "enabled, expected",
    [
        ({"wechat": True}, ["wechat"]),
        ({"telegram": True}, ["telegram"]),
        ({"wechat": True, "feishu": True}, ["wechat", "feishu"]),
        ({}, []),
        ({"wechat": False, "telegram": False}, []),
    ],
)
def test_falls_back_to_enabled_channels(enabled, expected):
    """28 个“无出厂渠道”的事件：只要用户配好了渠道，就应该收到。"""
    helper = NotificationPolicyHelper(_FakeDB(), _Cfg(enabled=enabled))
    assert helper.get_channels_for_event(1, "download_failed") == expected


def test_explicit_rule_wins_over_fallback():
    """显式规则优先于回退，不改变既有订阅语义。"""
    cfg = _Cfg(enabled={"wechat": True}, rules={"download_failed": ["dingtalk"]})
    helper = NotificationPolicyHelper(_FakeDB(), cfg)
    assert helper.get_channels_for_event(1, "download_failed") == ["dingtalk"]
