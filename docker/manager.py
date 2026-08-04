# 模块：docker/manager.py
# Docker 进程内 StandardManager 全局单例 — 所有 API 模块共享同一个实例
# 分隔
# 替代各模块各自 `_mgr = StandardManager()` 的做法，
# 确保 DB 连接、HTTP session、缓存、任务队列在同一个进程内唯一。

from pilotstd.manager.facade import StandardManager

_mgr = None


def get_manager() -> StandardManager:
    """返回进程内唯一的 StandardManager 实例（惰性初始化）。"""
    global _mgr
    if _mgr is None:
        _mgr = StandardManager()
    return _mgr


async def get_manager_dep() -> StandardManager:
    """FastAPI Depends() 依赖：返回进程内 StandardManager 单例。"""
    return get_manager()
