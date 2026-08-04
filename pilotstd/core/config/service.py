# 模块：统一配置访问层
"""统一配置访问入口。

路由规则：
  - 获取系统设置         → 配置文件加内存缓存
  - 获取用户偏好         → 用户偏好表加最近使用缓存
  - 设置用户偏好         → 校验前缀 → 写入键值表 → 清除缓存

三级回退：数据库记录 → 系统默认值 → 调用者传入的默认值
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from ..context import get_current_user_id
from ..db import Database
from .manager import ConfigManager
from .paths import get_db_path

logger = logging.getLogger(__name__)

# 保留前缀 —— 禁止用户写入
_RESERVED_PREFIXES = ("system.", "auth.", "role.")

# 用户偏好系统默认值 —— 数据库无记录时的兜底
_SYSTEM_DEFAULT_PREFS: dict[str, str] = {
    "ui.theme": "light",
    "ui.lang": "zh-CN",
}


class ConfigService:
    """统一配置访问：用户偏好（数据库）加系统设置（配置文件）。"""

    _instance: ConfigService | None = None
    _lock = threading.Lock()

    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        self._cfg = config_manager or ConfigManager()
        self._pref_cache: dict[str, str] = {}
        self._cache_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ConfigService:
        """线程安全的单例获取。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 系统设置 ──

    def get_system(self, key: str, default: Any = None) -> Any:
        return self._cfg.get(key, default)

    # ── 用户偏好 ──

    def _get_db(self) -> Database:
        return Database(get_db_path())

    def get_user_pref(self, key: str, default: Any = None, user_id: int | None = None) -> Any:
        """读取用户偏好，三级回退：数据库 → 系统默认值 → 参数默认值。"""
        uid = user_id or get_current_user_id()
        if uid is None:
            return default

        cache_key = f"user_pref:{uid}:{key}"
        with self._cache_lock:
            if cache_key in self._pref_cache:
                try:
                    return json.loads(self._pref_cache[cache_key])
                except (json.JSONDecodeError, TypeError):
                    return self._pref_cache[cache_key]

        db = self._get_db()
        row = db.fetchone(
            "SELECT preference_value FROM user_preferences WHERE user_id=? AND preference_key=?",
            (uid, key),
        )
        db.close()

        if row is not None:
            value = row["preference_value"]
            with self._cache_lock:
                self._pref_cache[cache_key] = value
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        # 回退到系统默认值
        if key in _SYSTEM_DEFAULT_PREFS:
            return _SYSTEM_DEFAULT_PREFS[key]

        return default

    def set_user_pref(self, key: str, value: Any, user_id: int | None = None) -> None:
        """写入用户偏好。拒绝系统、认证、角色前缀。"""
        uid = user_id or get_current_user_id()
        if uid is None:
            raise RuntimeError("No user_id in context")

        for prefix in _RESERVED_PREFIXES:
            if key.startswith(prefix):
                raise ValueError(f"Key '{key}' uses reserved prefix '{prefix}'")

        db = self._get_db()
        json_val = json.dumps(value, ensure_ascii=False)
        db.execute(
            "INSERT OR REPLACE INTO user_preferences"
            " (user_id, preference_key, preference_value, updated_at)"
            " VALUES (?, ?, ?, datetime('now', 'localtime'))",
            (uid, key, json_val),
        )
        db.close()

        cache_key = f"user_pref:{uid}:{key}"
        with self._cache_lock:
            self._pref_cache[cache_key] = json_val

    def invalidate_user_cache(self, user_id: int | None = None) -> None:
        """清除用户偏好缓存（写偏好时内部自动调用，外部无需手动管理）。"""
        with self._cache_lock:
            if user_id is None:
                self._pref_cache.clear()
            else:
                prefix = f"user_pref:{user_id}:"
                keys = [k for k in self._pref_cache if k.startswith(prefix)]
                for k in keys:
                    del self._pref_cache[k]
