# 模块：项目/核心//_常量脚本
# 常量+装饰器+异常类—从脚本拆分

from typing import Any, Callable

# 当前期望的表结构版本号（每次新增迁移+1）
CURRENT_SCHEMA_VERSION = 48  # v48: ensure user_layouts + user_settings tables (production hotfix)

# 迁移注册表：版本号→迁移函数（接收实例）
MIGRATIONS: dict[int, Callable[..., Any]] = {}


def migration(version: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：注册迁移函数到指定版本号。"""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        # 将迁移函数注册到全局输入输出字典，按版本号索引
        MIGRATIONS[version] = fn
        return fn

    return decorator


class DatabaseError(Exception):
    """数据库操作失败时抛出的通用异常，不暴露内部结构。"""

    pass
