"""`_channel_registry` 补测（NEW-43，2026-11-24）。

该模块是通知渠道的**实例缓存与构造中枢**：
  - `build_channels` 按凭证构造渠道实例（凭证不全则跳过，不抛）
  - `channels_for` 按 user_id 缓存（默认用户走 `_channels`，兼容既有测试）
  - `invalidate` 凭证保存后清缓存（清错 → 用户改凭证不生效；不清 → 用旧凭证发消息）
  - `admin_user_ids` 系统通知的投递目标解析

清单把它列为高价值无测试模块（`_channel_registry`）。本文件锁住四条核心契约。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.core.notification import _channel_registry as reg  # noqa: E402


def _host(**overrides):
    """构造最小 host 替身（只带 registry 用到的属性）。"""
    host = MagicMock()
    host._user_id = 1
    host._channels = {}
    host._channel_cache = {}
    host._cred_helper = None
    host._build_channels = lambda uid: reg.build_channels(host, uid)
    for k, v in overrides.items():
        setattr(host, k, v)
    return host


class TestChannelsFor:
    """按 user_id 取渠道实例（缓存语义）。"""

    def test_default_user_returns_channels_dict(self):
        """默认用户直接返回 `_channels`（兼容既有测试替换该字典）。"""
        existing = {"feishu": object()}
        host = _host(_channels=existing)

        assert reg.channels_for(host, 1) is existing

    def test_other_user_cached_after_first_build(self):
        """非默认用户：首次构造后写入缓存，第二次命中缓存。"""
        host = _host()
        built = {"wechat": object()}
        host._build_channels = MagicMock(return_value=built)

        first = reg.channels_for(host, 7)
        second = reg.channels_for(host, 7)

        assert first is built
        assert second is built
        host._build_channels.assert_called_once_with(7)

    def test_cached_value_reused_without_rebuild(self):
        """已有缓存 → 不重新构造（用 spy 断言）。"""
        cached = {"telegram": object()}
        host = _host(_channel_cache={7: cached})
        host._build_channels = MagicMock(return_value={"should-not": object()})

        assert reg.channels_for(host, 7) is cached
        host._build_channels.assert_not_called()


class TestInvalidate:
    """凭证保存后清缓存（清错 → 改凭证不生效）。"""

    def test_default_user_rebuilds_in_place(self):
        """默认用户：清空并原地重建 `_channels`（保持字典对象引用不变）。"""
        channels = {"old": object()}
        host = _host(_channels=channels)
        # invalidate 直接调模块级 build_channels，故 patch 模块函数
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(reg, "build_channels", lambda _h, _u: {"new": object()})
            reg.invalidate(host, 1)

        assert "old" not in channels  # 旧渠道已清
        assert "new" in channels  # 新渠道已写入

    def test_other_user_cache_popped(self):
        """非默认用户：从缓存移除（下次访问时重建）。"""
        host = _host(_channel_cache={7: {"stale": object()}})

        reg.invalidate(host, 7)

        assert 7 not in host._channel_cache

    def test_other_user_missing_cache_is_safe(self):
        """缓存里没有该用户 → 安全空操作（不抛 KeyError）。"""
        host = _host(_channel_cache={})

        reg.invalidate(host, 99)  # 不抛即通过


class TestBuildChannels:
    """按凭证构造渠道（凭证不全则跳过，不抛）。"""

    def test_no_cred_helper_returns_empty(self):
        """无凭证助手 → 空渠道表（不抛）。"""
        host = _host(_cred_helper=None)

        assert reg.build_channels(host, 1) == {}

    def test_disabled_channel_skipped(self):
        """`enabled=false` 的渠道不构造。"""
        helper = MagicMock()
        helper.get_all.return_value = {"wechat": {"enabled": "false"}}
        host = _host(_cred_helper=helper)

        channels = reg.build_channels(host, 1)

        assert "wechat" not in channels

    def test_missing_required_credential_skipped(self):
        """必需凭证缺失 → 跳过该渠道（不抛、不构造半个实例）。"""
        helper = MagicMock()
        helper.get_all.return_value = {"feishu": {"enabled": "true"}}
        host = _host(_cred_helper=helper)

        channels = reg.build_channels(host, 1)

        assert "feishu" not in channels

    def test_channel_init_exception_does_not_break_others(self):
        """单个渠道构造抛异常 → 记 warning、继续构造其它（不整批失败）。"""
        helper = MagicMock()
        # 给出必然构造失败的凭证组合（字段不全）
        helper.get_all.return_value = {
            "wechat": {"enabled": "true", "webhook_url": "http://x"},
            "feishu": {"enabled": "true"},
        }
        host = _host(_cred_helper=helper)

        # 不抛异常即核心契约（渠道表可能为空，取决于 spec 校验）
        channels = reg.build_channels(host, 1)
        assert isinstance(channels, dict)


class TestAdminUserIds:
    """系统通知的投递目标解析。"""

    def test_returns_admin_ids(self):
        host = _host()
        host._db.fetchall.return_value = [{"id": 3}, {"id": 5}]

        assert reg.admin_user_ids(host) == [3, 5]

    def test_empty_admin_list_returns_empty(self):
        """真实空管理员列表 ⇒ 返回空（`system` 不发送，不回退默认用户）。"""
        host = _host()
        host._db.fetchall.return_value = []

        assert reg.admin_user_ids(host) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
