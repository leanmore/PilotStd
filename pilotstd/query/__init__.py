# 公共模型和基础类在顶层导入（轻量）
from .adapters.base import BaseAdapter
from .cache import CacheRepository
from .engine import QueryEngine
from .models import BatchQueryStats, CacheEntry, QueryResult
from .rotator import SiteRotator, SiteState

__all__ = [
    "QueryResult", "BatchQueryStats", "CacheEntry",
    "BaseAdapter", "CacheRepository", "QueryEngine",
    "SiteRotator", "SiteState",
]


# 适配器懒加载（避免启动时加载 requests/bs4/lxml）
def _get_csres_adapter():
    from .adapters.csres import CsresAdapter
    return CsresAdapter


def _get_std_gov_adapter():
    from .adapters.std_gov import StdGovAdapter
    return StdGovAdapter


def _get_njbz365_adapter():
    from .adapters.njbz365 import Njbz365Adapter
    return Njbz365Adapter


def _get_hbba_adapter():
    from .adapters.hbba import HbbaAdapter
    return HbbaAdapter


def _get_iso_gov_adapter():
    from .adapters.iso_gov import IsoGovAdapter
    return IsoGovAdapter


def _get_mock_adapter():
    try:
        from .adapters.mock import MockQueryAdapter
        return MockQueryAdapter
    except ImportError:
        return None
