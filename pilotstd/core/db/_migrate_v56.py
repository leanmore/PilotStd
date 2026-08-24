# 模块：项目/核心/数据库/迁移_v56脚本
# v56：幂等补列——为缓存/索引表补齐版本化三列（D-1 修复）
# 背景：v23 迁移对 standard_info_cache 的 ALTER TABLE 在其惰性建表前执行
#       （表尚不存在）失败且被 except Exception: pass 静默吞掉，导致
#       cache_manager 读写缺列（source_version/data_state/last_accessed_at）
#       时抛 OperationalError（缓存写入中断、公告刷新静默失败）。
# 设计：遵循"迁移不可变铁律"——不动 v23，新增版本号做幂等兜底补列
#       （范式参考 v48/v50/v52）。PRAGMA 检查列存在性，缺失才 ALTER，
#       任何失败记录带堆栈的错误日志，禁止静默吞错。

import logging
from typing import Any

from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v56")

# 需补齐版本化三列的目标表（标准信息缓存 + 文件索引）
_TARGET_TABLES = ("standard_info_cache", "file_index")
# 列定义（与 v23 迁移及 cache_manager 读取完全一致）
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_version", "TEXT DEFAULT 'initial'"),
    ("data_state", "TEXT DEFAULT 'fresh'"),
    ("last_accessed_at", "TEXT"),
)


@migration(56)
def _migrate_v56_ensure_cache_version_columns(db: Any) -> None:
    """幂等补齐缓存/索引表的版本化三列（缺失才 ALTER，失败记录日志）。

    存量数据回填策略：ALTER ADD COLUMN 的 DEFAULT 子句自动为既有行填充
    默认值（source_version='initial'、data_state='fresh'、last_accessed_at=NULL），
    与 cache_manager 的读取约定一致，无需手工 UPDATE。
    """
    for table in _TARGET_TABLES:
        # 表不存在则跳过（新库由建表逻辑或后续迁移负责）
        exists = db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not exists:
            _log.info("v56: 表 %s 不存在，跳过补列", table)
            continue

        try:
            cols = {
                r["name"]
                for r in db.fetchall(f"PRAGMA table_info({table})")
            }
        except Exception:
            _log.exception("v56: 读取表 %s 结构失败", table)
            raise

        for col_name, col_def in _COLUMNS:
            if col_name in cols:
                _log.debug("v56: 表 %s 已含列 %s，跳过", table, col_name)
                continue
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                _log.info("v56: 表 %s 补列 %s (%s) 完成", table, col_name, col_def)
            except Exception:
                # 补列失败必须带完整堆栈可见，禁止静默吞错（D-1 根因）
                _log.exception("v56: 表 %s 补列 %s 失败", table, col_name)
                raise
