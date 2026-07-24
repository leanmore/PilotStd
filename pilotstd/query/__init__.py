# 公共模型和基础类在顶层导入（轻量）
from typing import Any, Optional, Type

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


# 适配器懒加载（避免启动时加载 requests/bs4/lxml）
def _get_csres_adapter() -> Type[Any]:
    """懒加载工标网适配器（CsresAdapter）。"""
    from .adapters.csres import CsresAdapter

    return CsresAdapter


def _get_std_gov_adapter() -> Type[Any]:
    """懒加载国家标准公开适配器（StdGovAdapter）。"""
    from .adapters.std_gov import StdGovAdapter

    return StdGovAdapter


def _get_njbz365_adapter() -> Type[Any]:
    """懒加载南京标准网适配器（Njbz365Adapter）。"""
    from .adapters.njbz365 import Njbz365Adapter

    return Njbz365Adapter


def _get_hbba_adapter() -> Type[Any]:
    """懒加载行业标准适配器（HbbaAdapter）。"""
    from .adapters.hbba import HbbaAdapter

    return HbbaAdapter


def _get_iso_gov_adapter() -> Type[Any]:
    """懒加载国际标准适配器（IsoGovAdapter）。"""
    from .adapters.iso_gov import IsoGovAdapter

    return IsoGovAdapter


def _get_mock_adapter() -> Optional[Type[Any]]:
    """懒加载 mock 适配器，供测试使用。未安装时返回 None。"""
    try:
        from .adapters.mock import MockQueryAdapter

        return MockQueryAdapter  # type: ignore[no-any-return]  # 动态导入类无精确类型
    except ImportError:
        return None


def _get_ttbz_adapter() -> Type[Any]:
    """懒加载团体标准适配器（TTBZAdapter）。"""
    from .adapters.ttbz import TTBZAdapter

    return TTBZAdapter


def _get_mee_adapter() -> Type[Any]:
    """懒加载生态环境部标准适配器（MEEAdapter）。"""
    from .adapters.mee import MEEAdapter

    return MEEAdapter


def _get_nrsis_adapter() -> Type[Any]:
    """懒加载自然资源标准适配器（NRSISAdapter）。"""
    from .adapters.nrsis import NRSISAdapter

    return NRSISAdapter


def _get_jtst_adapter() -> Type[Any]:
    """懒加载交通运输部标准适配器（JTSTAdapter）。"""
    from .adapters.jtst import JTSTAdapter

    return JTSTAdapter


def _get_ccsn_adapter() -> Type[Any]:
    """懒加载工程建设标准化协会适配器（CCSNAdapter）。"""
    from .adapters.ccsn import CCSNAdapter

    return CCSNAdapter


def _get_jjg_adapter() -> Type[Any]:
    """懒加载国家计量技术规范适配器（JJGAdapter）。"""
    from .adapters.jjg import JJGAdapter

    return JJGAdapter


def _get_sppt_adapter() -> Type[Any]:
    """懒加载食品安全国家标准适配器（SPPTAdapter）。"""
    from .adapters.sppt import SPPTAdapter

    return SPPTAdapter


def _get_gongbiaoku_adapter() -> Type[Any]:
    from .adapters.gongbiaoku import GongBiaoKuAdapter

    return GongBiaoKuAdapter


def _get_sppt_local_adapter() -> Type[Any]:
    """懒加载食品安全地方标准适配器（SPPTLocalAdapter）。"""
    from .adapters.sppt_local import SPPTLocalAdapter

    return SPPTLocalAdapter
