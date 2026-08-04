# 模块：项目/核心//____脚本
# 数据库模块—从脚本拆分为4个子模块

from . import migrations  # noqa: F401 — 触发 @migration 装饰器注册，确保 MIGRATIONS 非空
from ._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS, DatabaseError, migration
from .database import Database

__all__ = [
    "Database",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "migration",
    "DatabaseError",
]
