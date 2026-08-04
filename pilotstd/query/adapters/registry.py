# 模块：pilotstd/query/adapters/registry.py
# 适配器统一注册表 — #44/#48 单一数据源
# 所有查询适配器的类引用、站点名、实例化均从此读取
import logging

from .ahbz import AhbzAdapter
from .base import BaseAdapter
from .ccsn import CCSNAdapter
from .csres import CsresAdapter
from .cssn import CSSNAdapter
from .dbba import DbbaAdapter
from .energy import EnergyAdapter
from .gongbiaoku import GongBiaoKuAdapter
from .hbba import HbbaAdapter
from .iso_gov import IsoGovAdapter
from .jjg import JJGAdapter
from .jtst import JTSTAdapter
from .mee import MEEAdapter
from .miit import MIITAdapter
from .ncha import NCHAAdapter
from .njbz365 import Njbz365Adapter
from .nrsis import NRSISAdapter
from .sppt import SPPTAdapter
from .sppt_local import SPPTLocalAdapter
from .std_gov import StdGovAdapter
from .tdpress import TDPressAdapter
from .ttbz import TTBZAdapter

logger = logging.getLogger(__name__)

# 完整注册表：site_name → 适配器类
ALL_ADAPTERS: dict[str, type[BaseAdapter]] = {
    "ahbz": AhbzAdapter,
    "ccsn": CCSNAdapter,
    "csres": CsresAdapter,
    "cssn": CSSNAdapter,
    "dbba": DbbaAdapter,
    "energy": EnergyAdapter,
    "gongbiaoku": GongBiaoKuAdapter,
    "hbba": HbbaAdapter,
    "iso_gov": IsoGovAdapter,
    "jjg": JJGAdapter,
    "jtst": JTSTAdapter,
    "mee": MEEAdapter,
    "miit": MIITAdapter,
    "ncha": NCHAAdapter,
    "njbz365": Njbz365Adapter,
    "nrsis": NRSISAdapter,
    "sppt": SPPTAdapter,
    "sppt_local": SPPTLocalAdapter,
    "std_gov": StdGovAdapter,
    "tdpress": TDPressAdapter,
    "ttbz": TTBZAdapter,
}


def instantiate_all() -> tuple[list[BaseAdapter], list[str]]:
    """尝试实例化全部注册适配器。

    Returns:
        (active_adapters, disabled_names) — 成功实例化的列表 + 失败的名称列表
    """
    active: list[BaseAdapter] = []
    disabled: list[str] = []

    for name, cls in ALL_ADAPTERS.items():
        try:
            instance = cls()
            active.append(instance)
        except Exception as e:
            logger.error("适配器 [%s] 实例化失败，已禁用: %s", name, e)
            disabled.append(name)

    if disabled:
        logger.warning("共 %d 个适配器实例化失败，已从路由链中排除: %s", len(disabled), ", ".join(disabled))

    return active, disabled
