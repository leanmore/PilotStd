# 模块：项目/查询/站点配置（包入口）
# 统一导出站点配置符号，保持外部导入兼容。

from ._loader import create_default_sites, get_site_config
from ._profiles import ADAPTER_DEFAULT_PROFILES

__all__ = ["create_default_sites", "get_site_config", "ADAPTER_DEFAULT_PROFILES"]
