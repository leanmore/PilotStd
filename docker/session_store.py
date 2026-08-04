# 模块：docker/session_store.py
# 服务端会话存储 — JWT token 与用户会话映射，支持登出/刷新/过期清理
"""内存会话存储：记录活跃 token，支持主动登出和定期清理过期条目。"""

import threading
import time
from typing import Any


class SessionStore:
    """线程安全的服务端会话存储（单例）。"""

    _instance: "SessionStore | None" = None
    _lock = threading.Lock()  # 类级别锁，保护单例创建
    _store: dict[str, dict[str, Any]]
    _store_lock: threading.Lock  # 实例级别锁，保护会话字典的并发读写

    def __new__(cls) -> "SessionStore":
        # 双重检查锁定实现线程安全单例
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store = {}
                    cls._instance._store_lock = threading.Lock()
        return cls._instance

    def add(self, token: str, user_info: dict[str, Any], ttl_seconds: int = 7200) -> None:
        """记录新会话。ttl_seconds 默认 2 小时。"""
        now = time.time()
        with self._store_lock:
            self._store[token] = {
                "user_id": user_info.get("user_id", user_info.get("username", "")),
                "username": user_info.get("username", ""),
                "created_at": now,
                "expires_at": now + ttl_seconds,
            }

    def get(self, token: str) -> dict[str, Any] | None:
        """获取会话信息。若 token 不存在或已过期返回 None。"""
        now = time.time()
        with self._store_lock:
            session = self._store.get(token)
            if session is None:
                return None
            if session["expires_at"] <= now:
                del self._store[token]
                return None
            return session

    def remove(self, token: str) -> bool:
        """移除会话（登出时调用）。返回是否成功移除。"""
        with self._store_lock:
            if token in self._store:
                del self._store[token]
                return True
            return False

    def update_expiry(self, token: str, ttl_seconds: int = 7200) -> bool:
        """刷新会话过期时间（token 刷新时调用）。"""
        now = time.time()
        with self._store_lock:
            session = self._store.get(token)
            if session is None:
                return False
            session["expires_at"] = now + ttl_seconds
            return True

    def cleanup_expired(self) -> int:
        """清理所有过期会话。返回清理数量。"""
        now = time.time()
        removed = 0
        with self._store_lock:
            # 收集所有过期 token，批量删除
            expired = [t for t, s in self._store.items() if s["expires_at"] <= now]
            for t in expired:
                del self._store[t]
                removed += 1
        return removed

    @property
    def active_count(self) -> int:
        """返回当前活跃会话数（不含已过期但未清理的）。"""
        return len(self._store)


_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """获取全局会话存储实例（惰性初始化）。"""
    global _session_store
    # 惰性创建，首次调用时初始化
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
