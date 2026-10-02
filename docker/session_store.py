# 模块：容器/_脚本
# 服务端会话存储—令牌与用户会话映射，支持登出/刷新/过期清理
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

    def add(self, token: str, user_id: int, username: str = "", ttl_seconds: int = 7200) -> None:
        """记录新会话。ttl_seconds 默认 2 小时。

        **L-03 修复**：原签名为 `add(token, user_info: dict, ttl)`，内部用
        `user_info.get("user_id", user_info.get("username", ""))` 取 id —— 但全库 9 处调用
        **全部只传 `{"username": ...}`**，故 `session["user_id"]` 实际恒为**用户名字符串**，
        使"按 user_id 移除会话"永远匹配不到。现改为**显式 `user_id: int` 参数**：
        调用方无法再漏传，且类型在边界上即被约束。
        """
        now = time.time()
        with self._store_lock:
            self._store[token] = {
                "user_id": user_id,
                "username": username,
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

    def remove_by_user(self, user_id: int) -> int:
        """移除指定用户的**全部**会话，返回移除数量（L-03）。

        用于"改密后强制重新登录"：`users.change_password` 在落库成功后调用，使被窃取的
        旧 token 立即失效（而非等到 `expires_at`）。

        实现为**线性扫描** `_store`：其规模等于活跃会话数（个人项目通常个位数），
        故无需为 `user_id` 额外建索引——避免为极小 N 引入第二份需同步的状态。

        依赖 `add()` 写入的 `user_id` 为 **int**（与 `get_current_user_id()` 的返回类型一致），
        否则 `==` 比较失败；该不变量由 `add()` 的签名类型强制。
        """
        with self._store_lock:
            targets = [t for t, s in self._store.items() if s.get("user_id") == user_id]
            for t in targets:
                del self._store[t]
            return len(targets)

    def cleanup_expired(self) -> int:
        """清理所有过期会话。返回清理数量。"""
        now = time.time()
        removed = 0
        with self._store_lock:
            # 收集所有过期，批量删除
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
