# 模块：项目/核心/配置/____脚本
# 配置管理包 — 重导出所有公开符号，保持外部接口不变

from .defaults import FACTORY_DEFAULTS
from .manager import ConfigManager
from .paths import get_data_dir, get_db_path, get_library_root, get_network_timeout
from .service import ConfigService

__all__ = [
    "ConfigManager",
    "ConfigService",
    "FACTORY_DEFAULTS",
    "get_data_dir",
    "get_db_path",
    "get_library_root",
    "get_network_timeout",
]
