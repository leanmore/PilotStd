# 模块：容器/管理器脚本
# 进程内全局单例—所有接口模块共享同一个实例
# 分隔
# 替代各模块各自`_=()`的做法，
# 确保数据库连接、网络、缓存、任务队列在同一个进程内唯一。

import threading

from pilotstd.manager.facade import StandardManager

_mgr = None
_mgr_lock = threading.Lock()


def get_manager() -> StandardManager:
    """返回进程内唯一的 StandardManager 实例（并发安全惰性初始化）。"""
    global _mgr
    if _mgr is None:
        with _mgr_lock:
            if _mgr is None:
                _mgr = StandardManager()
    return _mgr


async def get_manager_dep() -> StandardManager:
    """FastAPI Depends() 依赖：返回进程内 StandardManager 单例。"""
    return get_manager()
