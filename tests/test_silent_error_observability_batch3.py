"""静默吞错第 3 批：缓存配置回退与 Qt 孤儿清理（体检 D-8）。

- `CacheManager._load_config_*` 读失败静默用默认值（配置可能被写坏而无感）；
- `qt_lifecycle._forget_orphan` 的 ValueError 被 pass（重复清理无痕迹）；
- `ui/workers/_common.close` 的 sip/removeHandler 失败被 pass。
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def cache():
    from pilotstd.core.cache_manager import CacheManager

    obj = object.__new__(CacheManager)
    obj._db = MagicMock()
    obj._db.fetchone.side_effect = RuntimeError("cache_config unreadable")
    return obj


def test_load_config_int_failure_logs(cache, caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.cache_manager"):
        assert cache._load_config_int("max_size_mb", 50) == 50
    assert "cache config max_size_mb unreadable" in caplog.text


def test_load_config_bool_failure_logs(cache, caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.cache_manager"):
        assert cache._load_config_bool("auto_cleanup", True) is True
    assert "cache config auto_cleanup unreadable" in caplog.text


def test_load_config_float_failure_logs(cache, caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.cache_manager"):
        assert cache._load_config_float("cleanup_ratio", 0.1) == 0.1
    assert "cache config cleanup_ratio unreadable" in caplog.text


def test_forget_orphan_not_registered_logs(caplog) -> None:
    from pilotstd.ui import qt_lifecycle

    with caplog.at_level(logging.DEBUG, logger="pilotstd.ui.qt_lifecycle"):
        qt_lifecycle._forget_orphan(object())
    assert "orphan worker not in registry" in caplog.text
