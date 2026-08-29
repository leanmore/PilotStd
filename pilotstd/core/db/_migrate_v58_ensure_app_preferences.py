# 模块：项目/核心/数据库/迁移_v58脚本
# v58：幂等补建 app_preferences 表（N-01 修复）
# 背景：v20 迁移在部分实例产生"空 checksum 占位"（版本号已记录但 DDL 未执行），
#       导致 app_preferences 表缺失 → auto_announce 每日 01:00 读取
#       announce_since_date 抛 OperationalError → 定时公告检查（及定时路径的
#       公告通知事件）永久中断。当前 CURRENT_SCHEMA_VERSION 已推进到 57，
#       v20 不会自动重跑，故新增 v58 显式补建（范式参考 v48/v50/v56/v57
#       的幂等 ensure 模式：迁移不可变铁律——不动 v20，新增版本号兜底）。
# 幂等性：CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE，任意库状态重复执行无副作用。
# 表结构与 v20 迁移定义完全一致（key/value/updated_at），不改变既有设计。

import logging
from typing import Any

from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v58")


@migration(58)
def _migrate_v58_ensure_app_preferences(db: Any) -> None:
    """幂等补建 app_preferences 表并写入 announce_since_date 默认值。

    表结构与 v20 迁移（_migrate_v16_v49._migrate_v20_announce_since_date）
    完全一致：key TEXT PRIMARY KEY / value TEXT / updated_at TEXT
    DEFAULT CURRENT_TIMESTAMP。缺失才建表，存在则跳过（IF NOT EXISTS）；
    默认行缺失才插入（INSERT OR IGNORE），重复执行无副作用。
    """
    db.execute(
        """CREATE TABLE IF NOT EXISTS app_preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute(
        "INSERT OR IGNORE INTO app_preferences (key, value) VALUES (?, ?)",
        ("announce_since_date", ""),
    )
    _log.info("v58: app_preferences 表已确保存在，announce_since_date 默认值已设置")
