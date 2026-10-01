"""共享实例 + 显式配置失效通知受控测试（#31-P1 / R14-3b，2026-10-01）。

锁定 `manager.get_shared_config()` / `invalidate_shared_config()` / 监听者注册表与
`ConfigManager.save()` 的失效发布语义：

  · 同一路径复用同一实例（线程安全）；
  · **他方实例**写盘（GUI 设置页 / Web API 各自持有的实例）→ 共享缓存被视为陈旧而移除 + 通知；
  · **自己**写盘 → 内存态即权威，保留缓存实例，但仍通知监听者；
  · 显式 `invalidate_shared_config()` → 移除 + 通知（返回是否命中）；
  · 监听者注册去重 / 注销生效 / 单个监听者异常被隔离；
  · **不存在基于时间的静默 TTL**：未发生写盘时实例跨时间复用（用户约束）。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from pilotstd.core.config import manager as cfgmod
from pilotstd.core.config.manager import (
    ConfigManager,
    get_shared_config,
    invalidate_shared_config,
    register_invalidation_listener,
    unregister_invalidation_listener,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """用例前后清空共享缓存与监听者，避免跨用例串扰（并还原原监听者集合）。"""
    with cfgmod._SHARED_LOCK:
        cfgmod._SHARED_INSTANCES.clear()
        original_listeners = list(cfgmod._INVALIDATION_LISTENERS)
    yield
    with cfgmod._SHARED_LOCK:
        cfgmod._SHARED_INSTANCES.clear()
        cfgmod._INVALIDATION_LISTENERS[:] = original_listeners


def _path(tmp_path) -> str:
    return os.path.abspath(str(tmp_path / "config.json"))


def test_get_shared_config_reuses_same_instance(tmp_path):
    """同一路径多次获取返回同一实例；不同路径各自独立。"""
    p1, p2 = _path(tmp_path), os.path.abspath(str(tmp_path / "other.json"))
    assert get_shared_config(p1) is get_shared_config(p1)
    assert get_shared_config(p1) is not get_shared_config(p2)


def test_get_shared_config_is_thread_safe(tmp_path):
    """并发首次获取只创建一个实例（双检锁）。"""
    path = _path(tmp_path)
    barrier = threading.Barrier(8)
    results: list[ConfigManager] = []

    def worker() -> None:
        barrier.wait()
        results.append(get_shared_config(path))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 8
    assert len({id(r) for r in results}) == 1, "并发获取必须拿到同一实例"


def test_no_time_based_ttl(tmp_path):
    """未发生写盘时实例跨时间复用——明确不存在静默 TTL 缓存。"""
    path = _path(tmp_path)
    first = get_shared_config(path)
    for _ in range(3):
        assert get_shared_config(path) is first


def test_foreign_write_drops_cache_and_notifies(tmp_path):
    """他方实例写盘（GUI 设置页式）→ 共享缓存被判陈旧并移除 + 通知监听者。"""
    path = _path(tmp_path)
    shared = get_shared_config(path)
    shared.set("query.sites.std_gov.default_weight", 70)
    shared.save()  # 建立基线（此时尚未注册监听者）

    seen: list[str] = []
    register_invalidation_listener(seen.append)

    gui = ConfigManager(path)  # 另一实例：等价于 GUI 设置页持有的 ConfigManager
    gui.set("query.sites.std_gov.default_weight", 99)
    gui.save()

    assert seen == [path], "写盘必须发布失效通知（路径口径＝绝对路径）"
    assert get_shared_config(path) is not shared, "他方写盘后共享缓存必须失效"
    assert get_shared_config(path).get("query.sites.std_gov.default_weight") == 99


def test_own_write_notifies_but_keeps_cache(tmp_path):
    """自己写盘：内存态即权威 → 保留缓存实例，但仍通知监听者。"""
    path = _path(tmp_path)
    shared = get_shared_config(path)
    seen: list[str] = []
    register_invalidation_listener(seen.append)

    shared.set("network.timeout", 42)
    shared.save()

    assert seen == [path]
    assert get_shared_config(path) is shared, "自己写盘不应丢弃自己的缓存实例"
    assert shared.get("network.timeout") == 42


def test_explicit_invalidate_returns_hit_and_notifies(tmp_path):
    """显式失效：命中返回 1、重复调用返回 0，且每次都通知。"""
    path = _path(tmp_path)
    get_shared_config(path)
    seen: list[str] = []
    register_invalidation_listener(seen.append)

    assert invalidate_shared_config(path) == 1
    assert invalidate_shared_config(path) == 0
    assert seen == [path, path]
    assert get_shared_config(path) is not None


def test_listener_registration_is_deduplicated_and_removable(tmp_path):
    """同一回调重复注册只生效一次；注销后不再收到通知。"""
    path = _path(tmp_path)
    shared = get_shared_config(path)
    seen: list[str] = []

    register_invalidation_listener(seen.append)
    register_invalidation_listener(seen.append)
    shared.save()
    assert len(seen) == 1, "同一回调不得重复注册"

    unregister_invalidation_listener(seen.append)
    shared.save()
    assert len(seen) == 1, "注销后不应再收到通知"


def test_listener_exception_is_isolated(tmp_path):
    """单个监听者抛异常不得影响其它监听者，也不得中断写盘主流程。"""
    path = _path(tmp_path)
    shared = get_shared_config(path)
    seen: list[str] = []

    def _boom(_path: str) -> None:
        raise RuntimeError("listener boom")

    register_invalidation_listener(_boom)
    register_invalidation_listener(seen.append)

    shared.set("network.timeout", 7)
    shared.save()

    assert seen == [path], "异常监听者不得阻断后续监听者"
    assert Path(path).exists()


def test_default_config_path_matches_constructor(tmp_path, monkeypatch):
    """`get_shared_config()` 的缺省路径与 `ConfigManager()` 的缺省路径同口径。"""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr("pilotstd.core.config.paths._get_config_dir", lambda: str(cfg_dir))

    default_path = os.path.abspath(str(cfg_dir / "config.json"))
    assert cfgmod.default_config_path() == default_path
    assert get_shared_config()._filepath == default_path
    assert ConfigManager()._filepath == default_path
