# pilotstd/core/db/__init__.py
# 数据库模块 — 从 db.py 拆分为 4 个子模块

from ._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS, DatabaseError, migration
from .database import Database

__all__ = [
    "Database",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "migration",
    "DatabaseError",
]
