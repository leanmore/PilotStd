# 模块：pilotstd/ui/core/handlers/settings_io_flow_engine.py
"""SettingsConfigIOEngine — 设置配置的序列化/反序列化纯逻辑层（零 Qt 依赖）。

将 SettingsConfigIO 中的键值映射与默认值回填逻辑提取为纯静态方法，
Handler 仅负责 Qt 控件 ↔ dict 的数据搬运。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════ 分隔
# 常量（Handler 层的唯一真相源）
# ═══════════════════════════════════════════════════════════════ 分隔

# 图标主题选项映射（显示名 → 内部键）
ICON_OPTIONS: dict[str, str] = {
    "默认": "default",
    "指南针": "compass_book",
    "放大镜": "magnifier_check",
    "灯塔": "lighthouse_folder",
}

# 语言代码列表，按 ComboBox 索引对应
LANG_CODES: list[str] = ["zh_CN", "zh_TW", "en"]

# OCR 凭证字段定义：(Handler 属性名, 配置键, 占位提示)
OCR_CREDENTIAL_FIELDS: list[tuple[str, str, str]] = [
    ("_ocr_api_key", "ocr.baidu_api_key", "百度云 API Key"),
    ("_ocr_secret_key", "ocr.baidu_secret_key", "百度云 Secret Key"),
    ("_ocr_secret_id", "ocr.tencent_secret_id", "腾讯云 Secret ID"),
    ("_ocr_tencent_secret_key", "ocr.tencent_secret_key", "腾讯云 Secret Key"),
    ("_ocr_access_key_id", "ocr.aliyun_access_key_id", "阿里云 Access Key ID"),
    ("_ocr_access_key_secret", "ocr.aliyun_access_key_secret", "阿里云 Access Key Secret"),
]


class SettingsConfigIOEngine:
    """设置配置的纯逻辑序列化/反序列化。

    所有类常量 DEFAULT_* 为对应配置组的默认值字典。
    serialize_* / deserialize_* 均为无状态静态方法。
    """

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 默认值常量（配置项唯一真相源）
    # ═══════════════════════════════════════════════════════════════ 分隔

    DEFAULT_GENERAL: dict[str, Any] = {
        "appearance.language": "zh_CN",
        "appearance.skip_welcome": False,
        "appearance.hyphen_style": True,
        "appearance.column_visibility": [True] * 9,
    }

    DEFAULT_APPEARANCE: dict[str, Any] = {
        "appearance.theme": "经典白",
        "appearance.icon_theme": "default",
    }

    DEFAULT_LIBRARY: dict[str, Any] = {
        "storage.root_dir": "",
        "storage.expire_folder": "过期作废",
        "storage.downloads_dir": "",
        "organize.auto_clean_source": False,
        "storage.mirror_skipped_dirs": True,
        "storage.mirror_fallback": True,
        "watchdog.enabled": False,
        "file.clear_readonly": True,
        "scan.skip_folders": ["过期作废"],
        "scan.extensions": [".pdf", ".doc", ".docx", ".txt"],
        "scan.exclude_patterns": [
            "征求意见稿",
            "培训课件",
            "建设项目过程资料及交工资料标准",
            "吊车性能",
            "标准图集",
        ],
    }

    DEFAULT_ADVANCED: dict[str, Any] = {
        "network.proxy": "",
        "network.ua_rotation": True,
        "announcement.enabled": False,
        "query.use_cache": True,
        "query.use_announcement_match": False,
        "query.announcement_url": "http://localhost:9028",
        "query.announcement_api_key": "",
        "ocr.baidu_api_key": "",
        "ocr.baidu_secret_key": "",
        "ocr.tencent_secret_id": "",
        "ocr.tencent_secret_key": "",
        "ocr.aliyun_access_key_id": "",
        "ocr.aliyun_access_key_secret": "",
    }

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 内部辅助
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def _fill_missing(data: Any, defaults: dict[str, Any]) -> dict[str, Any]:
        """用 defaults 填充 data 中缺失或类型错误的键，返回新 dict。

        data 中存在的键优先使用，缺失或类型不匹配时回退到 defaults。
        """
        result = dict(defaults)
        if not isinstance(data, dict):
            return result
        for key in defaults:
            if key in data:
                val = data[key]
                default_val = defaults[key]
                # 类型一致性检查：类型不同时回退默认值
                if type(val) is type(default_val):
                    result[key] = val
                elif default_val is not None:
                    result[key] = default_val
        return result

    # ═══════════════════════════════════════════════════════════════ 分隔
    # General — 语言、启动行为
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_general(data: dict[str, Any]) -> dict[str, Any]:
        """序列化通用设置，缺失键从 DEFAULT_GENERAL 回填。"""
        return SettingsConfigIOEngine._fill_missing(data, SettingsConfigIOEngine.DEFAULT_GENERAL)

    @staticmethod
    def deserialize_general(data: dict[str, Any] | None, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """反序列化通用设置；default 可覆盖 DEFAULT_GENERAL 中的特定键。"""
        base = dict(SettingsConfigIOEngine.DEFAULT_GENERAL)
        if isinstance(default, dict):
            for k in base:
                if k in default:
                    base[k] = default[k]
        return SettingsConfigIOEngine._fill_missing(data, base)

    # ═══════════════════════════════════════════════════════════════ 分隔
    # Appearance — 主题、图标
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_appearance(data: dict[str, Any]) -> dict[str, Any]:
        """序列化外观设置。"""
        return SettingsConfigIOEngine._fill_missing(data, SettingsConfigIOEngine.DEFAULT_APPEARANCE)

    @staticmethod
    def deserialize_appearance(data: dict[str, Any] | None, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """反序列化外观设置。"""
        base = dict(SettingsConfigIOEngine.DEFAULT_APPEARANCE)
        if isinstance(default, dict):
            for k in base:
                if k in default:
                    base[k] = default[k]
        return SettingsConfigIOEngine._fill_missing(data, base)

    # ═══════════════════════════════════════════════════════════════ 分隔
    # Library — 存储路径、扫描选项
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_library(data: dict[str, Any]) -> dict[str, Any]:
        """序列化资源库设置。"""
        return SettingsConfigIOEngine._fill_missing(data, SettingsConfigIOEngine.DEFAULT_LIBRARY)

    @staticmethod
    def deserialize_library(data: dict[str, Any] | None, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """反序列化资源库设置。"""
        base = dict(SettingsConfigIOEngine.DEFAULT_LIBRARY)
        if isinstance(default, dict):
            for k in base:
                if k in default:
                    base[k] = default[k]
        return SettingsConfigIOEngine._fill_missing(data, base)

    # ═══════════════════════════════════════════════════════════════ 分隔
    # Advanced — 网络代理、OCR 密钥、缓存
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_advanced(data: dict[str, Any]) -> dict[str, Any]:
        """序列化高级设置。"""
        return SettingsConfigIOEngine._fill_missing(data, SettingsConfigIOEngine.DEFAULT_ADVANCED)

    @staticmethod
    def deserialize_advanced(data: dict[str, Any] | None, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """反序列化高级设置。"""
        base = dict(SettingsConfigIOEngine.DEFAULT_ADVANCED)
        if isinstance(default, dict):
            for k in base:
                if k in default:
                    base[k] = default[k]
        return SettingsConfigIOEngine._fill_missing(data, base)

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 图标主题映射
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def get_icon_internal_key(display_name: str) -> str:
        """显示名 → 内部键，未匹配返回 'default'。"""
        return ICON_OPTIONS.get(display_name, "default")

    @staticmethod
    def get_icon_display_name(internal_key: str) -> str:
        """内部键 → 显示名，未匹配返回 '默认'。"""
        reverse = {v: k for k, v in ICON_OPTIONS.items()}
        return reverse.get(internal_key, "默认")

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 语言代码
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def resolve_language_code(combo_index: int) -> str:
        """ComboBox 索引 → 语言代码，越界返回 'zh_CN'。"""
        if 0 <= combo_index < len(LANG_CODES):
            return LANG_CODES[combo_index]
        return "zh_CN"

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 文本解析
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def parse_comma_separated(text: str) -> list[str]:
        """逗号分隔文本 → 去空白字符串列表，空字符串返回空列表。"""
        if not text or not text.strip():
            return []
        return [s.strip() for s in text.split(",") if s.strip()]

    @staticmethod
    def parse_comma_separated_with_fallback(text: str, fallback: list[str]) -> list[str]:
        """解析逗号分隔文本，结果为空时返回 fallback。"""
        result = SettingsConfigIOEngine.parse_comma_separated(text)
        return result if result else list(fallback)
