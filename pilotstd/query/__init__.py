# 查询模型和缓存层在二层导入，避免循环
from .adapters.base import BaseAdapter
from .cache import CacheRepository
from .engine import QueryEngine
from .models import BatchQueryStats, CacheEntry, QueryResult
from .rotator import SiteRotator, SiteState

__all__ = [
    "QueryResult",
    "BatchQueryStats",
    "CacheEntry",
    "BaseAdapter",
    "CacheRepository",
    "QueryEngine",
    "SiteRotator",
    "SiteState",
]

# 适配器统一从 `adapters/registry.py` 导出（A-33，2026-11-14）：
# 原 20 个 `_get_*_adapter` 懒加载函数已删除——生产 0 调用、唯一消费者是
# `tests/test_query_init.py` 自己锁自己，且会绕过 `registry` 的单一真相源。
# 新增适配器请登记 `ALL_ADAPTERS`，不要在本模块再加同类 `getter`。
