# 模块：pilotstd/manager/settings_manager.py
# 用户偏好管理器（Web 端）— 使用 user_settings 表（JSON 聚合存储），带内存缓存

import json
import logging
from copy import deepcopy
from typing import Any, Dict, Optional

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database

logger = logging.getLogger(__name__)
# UserPreferenceManager — 用户偏好管理器，参考 MoviePilot SystemConfigOper 的内存缓存模式


class UserPreferenceManager:
    """用户偏好管理器，参考 MoviePilot SystemConfigOper 的内存缓存模式"""

    _cache: Dict[int, Dict[str, Any]] = {}

    DEFAULT_PREFERENCES: Dict[str, Any] = {
        "ui": {
            "theme": "light",
            "language": "zh-CN",
            "compact_mode": False,
            "items_per_page": 20,
        },
        "search": {
            "default_standard_type": "GB/T",
            "auto_open_details": True,
            "recent_limit": 10,
        },
        "notifications": {
            "email_enabled": True,
            "desktop_popup": True,
            "sound_enabled": False,
        },
        "download": {
            "auto_organize": True,
            "overwrite": False,
        },
        "layouts": {
            "home": {},
            "search": {},
            "detail": {},
        },
    }

    @classmethod
    def _get_db(cls) -> Database:
        """获取数据库连接（每次调用新建，避免连接状态污染）。"""
        return Database(get_db_path())

    @classmethod
    def _ensure_table_exists(cls, db: Database) -> None:
        """确保 user_settings 表存在（与旧 user_preferences KV 表并存，不冲突）"""
        result = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
        if result:
            return
        db.execute("""
            CREATE TABLE user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                settings JSON NOT NULL DEFAULT '{}',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        db.execute("CREATE INDEX idx_user_settings_user_id ON user_settings(user_id)")
        logger.info("已创建 user_settings 表")

    @classmethod
    # get_preferences — 获取用户完整偏好（合并默认值），优先读缓存
    def get_preferences(cls, user_id: int) -> Dict[str, Any]:
        """获取用户完整偏好（合并默认值），优先读缓存"""
        if user_id in cls._cache:
            return deepcopy(cls._cache[user_id])

        db = cls._get_db()
        cls._ensure_table_exists(db)

        row = db.fetchone(
            "SELECT settings FROM user_settings WHERE user_id = ?",
            (user_id,),
        )

        if row:
            user_prefs = json.loads(row["settings"])
        else:
            user_prefs = {}
            db.execute(
                "INSERT INTO user_settings (user_id, settings) VALUES (?, '{}')",
                (user_id,),
            )

        merged = cls._deep_merge(cls.DEFAULT_PREFERENCES, user_prefs)
        cls._cache[user_id] = merged
        return deepcopy(merged)

    @classmethod
    def update_preferences(cls, user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """增量更新用户偏好（只传需要修改的字段）"""
        current = cls.get_preferences(user_id)
        cls._deep_update(current, updates)

        db = cls._get_db()
        db.execute(
            "UPDATE user_settings SET settings = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (json.dumps(current), user_id),
        )

        cls._cache[user_id] = current
        return deepcopy(current)

    @classmethod
    def reset_preferences(cls, user_id: int) -> Dict[str, Any]:
        """重置用户偏好到默认值"""
        db = cls._get_db()
        db.execute(
            "UPDATE user_settings SET settings = '{}', updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
        cls.clear_cache(user_id)
        return cls.get_preferences(user_id)

    @classmethod
    def clear_cache(cls, user_id: Optional[int] = None) -> None:
        """清除缓存（user_id 为 None 则清除全部）"""
        if user_id is None:
            cls._cache.clear()
        elif user_id in cls._cache:
            del cls._cache[user_id]

    @staticmethod
    def _deep_merge(defaults: dict, overrides: dict) -> dict:
        """递归合并字典，overrides 中缺失的默认字段补全"""
        result = deepcopy(defaults)
        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = UserPreferenceManager._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    @staticmethod
    def _deep_update(source: dict, updates: dict) -> None:
        """递归更新字典（原地修改）"""
        for key, value in updates.items():
            if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                UserPreferenceManager._deep_update(source[key], value)
            else:
                source[key] = deepcopy(value)
