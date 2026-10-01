# 模块：项目/查询/站点配置/加载器
# 站点配置唯一运行时出口（合并默认值 + config.json 覆盖）。

from typing import Any

from pilotstd.core.config.manager import register_invalidation_listener

from ..rotator import SiteState
from ._sites import (
    _create_sites_part1,
    _create_sites_part1b,
    _create_sites_part2,
    _create_sites_part3,
)


def create_default_sites() -> list[SiteState]:
    """创建默认站点配置并应用 config.json 的 UI 覆盖，返回 SiteState 列表。

    这是站点配置的唯一运行时出口：评分器与配额追踪器都从这里读取，
    保证 UI 修改（config.json 的 query.sites）与硬编码默认值单一来源对齐。
    """
    sites = _create_sites_part1() + _create_sites_part1b() + _create_sites_part2() + _create_sites_part3()
    overrides = _load_site_overrides()
    for site in sites:
        ov = overrides.get(site.name, {})
        # config.json 的 key 与 SiteState 字段名不一致，需逐一映射
        if ov.get("daily_limit") is not None:
            site.daily_limit = ov["daily_limit"]
        if ov.get("window_limit") is not None:  # UI 写入的 key 是 window_limit
            site.max_requests = ov["window_limit"]
        if ov.get("cooling_seconds") is not None:  # UI 写入的 key 是 cooling_seconds
            site.cooldown_seconds = ov["cooling_seconds"]
        if ov.get("request_interval") is not None:
            site.request_interval = ov["request_interval"]
    return sites


def _load_site_overrides() -> dict[str, Any]:
    """从 config.json 读取 query.sites 覆盖值，容错返回空 dict。

    #31-P1：改用按路径共享的 ConfigManager 实例（原为每次新建），与评分器同一来源。
    """
    try:
        from pilotstd.core.config.manager import get_shared_config

        sites = get_shared_config().get("query.sites", {})
        return sites if isinstance(sites, dict) else {}
    except Exception:
        return {}


# 站点配置缓存：create_default_sites 每次调用会重读 config.json，此处缓存避免重复开销
_site_config_cache: dict[str, SiteState] | None = None


def _on_config_invalidated(path: str) -> None:
    """配置写盘后的显式失效回调：清空站点缓存，使下次读取合并最新覆盖值。

    #31-P1（R14-3b）：GUI 设置页/Web API 写盘 → `ConfigManager.save()` 发布失效通知 →
    本回调清缓存 → 热路径下次取站点配置即刷新。**不做 TTL 静默缓存**（避免掩盖 bug）。
    """
    global _site_config_cache
    _site_config_cache = None


# 模块导入时注册一次（register_invalidation_listener 内部去重，重复导入不会重复注册）
register_invalidation_listener(_on_config_invalidated)


def get_site_config(name: str) -> SiteState | None:
    """按名称返回站点配置（含 search_url/probe_url），供适配器与健康检查读取。

    未找到返回 None，调用方需自行回退到硬编码值或 base_url。
    """
    global _site_config_cache
    if _site_config_cache is None:
        _site_config_cache = {s.name: s for s in create_default_sites()}
    return _site_config_cache.get(name)
