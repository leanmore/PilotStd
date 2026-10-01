"""热路径配置复用与失效刷新受控测试（#31-P1 / R14-3b，2026-10-01）。

背景：`pilotstd/query/routing/scorer.py::get_profile()` 原为“每次调用新建 ConfigManager”
（单批查询实测 133 次构造）。P1 改为按路径共享实例 + 写盘触发的显式失效通知。

覆盖：
  ① 热路径 50 次调用只构造 ≤2 次（冷启动 1 次共享实例；稳态 0 次）；
  ② 端到端失效：GUI 式独立实例写盘 → 热路径读到新值；
  ③ 站点配置缓存（`site_config/_loader.py`）在写盘后被显式清空 → 覆盖值生效。
"""

from __future__ import annotations

import pytest

from pilotstd.core.config.manager import ConfigManager, get_shared_config, invalidate_shared_config
from pilotstd.query.routing import scorer


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """把默认配置路径指向临时目录（`default_config_path()` 惰性读 `_get_config_dir`）。"""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr("pilotstd.core.config.paths._get_config_dir", lambda: str(cfg_dir))
    invalidate_shared_config()
    yield cfg_dir / "config.json"
    invalidate_shared_config()


def test_hot_path_reuses_shared_instance(tmp_config, monkeypatch):
    """热路径 50 次调用只构造 1 次共享实例；稳态再 50 次零构造。"""
    calls: list[int] = []
    original_init = ConfigManager.__init__

    def _counting_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(1)
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(ConfigManager, "__init__", _counting_init)

    profile = scorer.get_profile("std_gov")
    assert profile.get("default_weight") == 70, "基线默认值应可读到（证明路径真的跑通）"

    for _ in range(50):
        scorer.get_profile("std_gov")
    cold = len(calls)
    assert cold <= 2, f"冷启动构造次数应 ≤2，实测 {cold}"

    for _ in range(50):
        scorer.get_profile("std_gov")
    assert len(calls) - cold == 0, "稳态下不得再构造 ConfigManager"


def test_hot_path_sees_new_value_after_gui_write(tmp_config):
    """端到端失效：GUI 式独立实例写盘 → 热路径读到新覆盖值（无 TTL，靠显式通知）。"""
    assert scorer.get_profile("std_gov").get("default_weight") == 70

    gui_like = ConfigManager(str(tmp_config))  # GUI 设置页持有的独立实例
    gui_like.set("query.sites.std_gov.default_weight", 99)
    gui_like.save()

    assert scorer.get_profile("std_gov").get("default_weight") == 99, "写盘后热路径必须读到新值"


def test_shared_config_write_keeps_hot_path_consistent(tmp_config):
    """经共享实例写盘（自己写）后，热路径同样立即读到新值。"""
    shared = get_shared_config()
    shared.set("query.sites.std_gov.default_weight", 55)
    shared.save()

    assert scorer.get_profile("std_gov").get("default_weight") == 55


def test_site_config_cache_is_cleared_on_write(tmp_config):
    """站点配置缓存（模块级 `_site_config_cache`）由失效通知清空 → 覆盖值生效。"""
    from pilotstd.query.site_config import _loader

    before = _loader.get_site_config("std_gov")
    assert before is not None, "站点配置应可读取（缓存建立）"
    assert _loader._site_config_cache is not None, "首次读取后应已建立缓存"

    # UI 写入的 key 是 window_limit → 映射到 SiteState.max_requests
    gui_like = ConfigManager(str(tmp_config))
    gui_like.set("query.sites.std_gov.window_limit", 123)
    gui_like.save()

    assert _loader._site_config_cache is None, "写盘后站点缓存必须被显式清空"
    after = _loader.get_site_config("std_gov")
    assert after is not None and after.max_requests == 123, "覆盖值必须在重建后生效"
