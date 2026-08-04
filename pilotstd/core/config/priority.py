# 模块：pilotstd/core/config/priority.py
# 配置优先级管理器 — 在现有 ConfigManager 基础上提供 ENV > FILE > FACTORY 优先级查询

import json
import logging
import os
from enum import IntEnum
from typing import Any, Dict, Optional, Tuple

# 使用标准 logging 而非 LoggerManager，因为此模块可能在 LoggerManager 初始化前被加载
logger = logging.getLogger(__name__)


class ConfigPriority(IntEnum):
    """配置优先级（数值越大优先级越高）"""

    FACTORY = 0  # 硬编码默认值，最低优先级
    FILE = 1  # config.json 文件值
    ENV_LEGACY = 2  # 旧变量名（如 STANDARD_ROOT），保留向后兼容
    ENV_NEW = 2  # PILOTSTD_ 前缀环境变量，与旧变量同优先级但优先匹配


class PriorityConfigManager:
    """带优先级的配置管理器，与现有 ConfigManager 并存不冲突"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化优先级配置管理器：加载工厂默认值 → 文件配置 → 环境变量。"""
        # config_path 支持通过环境变量 PILOTSTD_CONFIG_PATH 覆盖，便于 Docker 场景
        self.config_path: str = config_path or os.getenv("PILOTSTD_CONFIG_PATH") or "config.json"
        # 缓存层：存储已解析的 (值, 优先级) 元组，避免重复查找
        self._cache: Dict[str, Tuple[Any, ConfigPriority]] = {}
        self._file_config: Dict[str, Any] = {}
        self._factory_defaults: Dict[str, Any] = {}
        self._env_new: Dict[str, Any] = {}
        self._env_legacy: Dict[str, Any] = {}

        # 按优先级从低到高依次加载，高优先级覆盖低优先级
        self._load_factory_defaults()
        self._load_file_config()
        self._load_env_config()

    def _load_factory_defaults(self) -> None:
        """加载硬编码的工厂默认值。"""
        # 这些是最底层的兜底值，仅在文件和环境变量都未设置时生效
        self._factory_defaults = {
            "STANDARD_ROOT": "/data/standards",
            "OCR_ENABLED": False,
            "MAX_UPLOAD_SIZE": 10 * 1024 * 1024,
            "DEFAULT_STANDARD_TYPE": "GB/T",
            "PAGE_SIZE": 20,
            "LOG_LEVEL": "INFO",
        }

    def _load_file_config(self) -> None:
        """从 config.json 文件加载配置（优先级高于工厂默认值）。"""
        # 文件不存在属于正常情况（首次运行），不记录错误日志
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._file_config = json.load(f)
            except Exception as e:
                logger.warning("加载配置文件失败: %s", e)

    def _load_env_config(self) -> None:
        """从环境变量加载配置：PILOTSTD_ 前缀优先，旧变量名兼容。"""
        self._env_new = {}
        self._env_legacy = {}

        # 旧版兼容变量名集合，v0.6 后推荐统一使用 PILOTSTD_ 前缀
        legacy_vars = {
            "STANDARD_ROOT",
            "OCR_BAIDU_API_KEY",
            "OCR_BAIDU_SECRET_KEY",
            "ADMIN_PASSWORD",
            "SUPERUSER",
        }

        for env_key, env_value in os.environ.items():
            if env_key.startswith("PILOTSTD_"):
                # 去掉 PILOTSTD_ 前缀作为配置键名，保持层级一致性
                config_key = env_key[9:]  # 去掉 "PILOTSTD_" 前缀
                self._env_new[config_key] = self._parse_env_value(env_value)
            elif env_key in legacy_vars:
                self._env_legacy[env_key] = self._parse_env_value(env_value)

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        """解析环境变量字符串值为 Python 类型（bool/int/str）。"""
        # 环境变量均为字符串，需根据内容推断实际类型
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        if value.isdigit():
            return int(value)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """按优先级获取配置值"""
        # 命中缓存直接返回，避免重复遍历四层数据源
        if key in self._cache:
            return self._cache[key][0]

        # 按优先级从高到低排列，新 ENV > 旧 ENV > FILE > FACTORY
        sources = [
            (self._env_new, ConfigPriority.ENV_NEW),
            (self._env_legacy, ConfigPriority.ENV_LEGACY),
            (self._file_config, ConfigPriority.FILE),
            (self._factory_defaults, ConfigPriority.FACTORY),
        ]

        for source_dict, _priority in sources:
            if key in source_dict:
                value = source_dict[key]
                # 写入缓存，下次命中时直接返回
                self._cache[key] = (value, _priority)
                return value

        return default

    def get_with_source(self, key: str) -> Dict[str, Any]:
        """获取配置值及其来源（调试用）"""
        self.get(key)  # 触发加载到缓存
        if key in self._cache:
            _val, priority = self._cache[key]
            return {"value": _val, "source": priority.name}
        return {"value": None, "source": "NOT_FOUND"}

    def set_file(self, key: str, value: Any) -> bool:
        """写入 config.json（仅非敏感配置）"""
        self._file_config[key] = value
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._file_config, f, indent=2, ensure_ascii=False)
            # 写入成功后立即更新缓存，保证后续读取一致性
            self._cache[key] = (value, ConfigPriority.FILE)
            return True
        except Exception as e:
            logger.error("写入配置文件失败: %s", e)
            return False

    def reload(self) -> None:
        """重新加载配置文件"""
        # 清空缓存后重新加载，用于运行时修改了配置文件或环境变量的场景
        self._cache.clear()
        self._load_file_config()
        self._load_env_config()

    def get_all_effective(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置的最终生效值及来源（调试用）"""
        result: Dict[str, Dict[str, Any]] = {}
        # 收集所有已知键名（四层来源的并集）
        all_keys: set = set()
        all_keys.update(self._factory_defaults.keys())
        all_keys.update(self._file_config.keys())
        all_keys.update(self._env_new.keys())
        all_keys.update(self._env_legacy.keys())

        for key in sorted(all_keys):
            result[key] = self.get_with_source(key)

        return result


# ── 全局单例 ──
# 模块级惰性初始化，首次调用 get_priority_config() 时创建实例
_default_manager: Optional[PriorityConfigManager] = None


def get_priority_config() -> PriorityConfigManager:
    """获取全局 PriorityConfigManager 实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = PriorityConfigManager()
    return _default_manager
