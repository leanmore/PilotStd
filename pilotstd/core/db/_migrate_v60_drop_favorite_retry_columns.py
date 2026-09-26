# 模块：项目/核心/数据库/迁移_v60脚本
# v60：删除 user_favorites 的归档重试死列（archive_retry_count / last_archive_attempt）
# 背景：两列由 v36 引入、v52/v59 兜底补建，唯一读取方是 `/api/favorites/{record_id}/status`
#       的 5 个旧响应键（local_path/error_message/in_cooldown/abandoned/archive_retry_count）。
#       技术债 #16 删掉旧键后（TD-16，2026-09-25），全库生产代码对这两列已零读取
#       （grep 命中仅剩 `_migrate_v31_plus.py`(v36) / `_migrate_v44.py` / `_migrate_v52.py` /
#       `_migrate_v59_ensure_favorite_retry_columns.py` 这些历史迁移与本文件），故属死列，
#       按 #16 残留清理。
# 铁律：已执行迁移源码不可变（P-106，改动会触发 checksum 不匹配导致库无法启动），
#       故不动 v36/v52/v59，用新增版本号做删除（同 v48/v50/v52/v56/v57/v58/v59 的追加范式）。
# 幂等性：先读 PRAGMA 列清单，缺失即跳过；表不存在同样跳过——迁移重跑零副作用。

import logging
import sqlite3
from typing import Any

from ._constants import DatabaseError, migration

_log = logging.getLogger("pilotstd.db.migrate.v60")

# 动态表名/列名一律取本文件全大写常量，禁止外部数据拼入（R-009）
_TABLE = "user_favorites"
_DROP_COLUMNS = ("archive_retry_count", "last_archive_attempt")


@migration(60)
def _migrate_v60_drop_favorite_retry_columns(db: Any) -> None:
    """删除 user_favorites.last_archive_attempt / archive_retry_count（幂等，可重复执行）。

    表不存在 → 跳过（故障库只含部分表的场景，同 v53/v57 的防御口径）。
    列不存在 → 跳过（迁移重跑或本来就没有这两列的库）。
    DROP 本身失败 → 降级为告警：两列零读取方，留下它们只是 schema 未收敛，
    不影响任何功能；而抛异常会让 `_run_migrations()` 抛 DatabaseError 直接阻断
    整个应用启动（database.py:180），代价远大于收益。
    """
    table = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (_TABLE,))
    if not table:
        _log.info("v60: 表 %s 不存在，跳过删列", _TABLE)
        return

    cols = {r["name"] for r in db.fetchall(f"PRAGMA table_info({_TABLE})")}
    dropped: list[str] = []
    for col in _DROP_COLUMNS:
        if col not in cols:
            continue
        try:
            db.execute(f"ALTER TABLE {_TABLE} DROP COLUMN {col}")
            dropped.append(col)
        except (sqlite3.OperationalError, DatabaseError) as exc:
            # 旧 SQLite（< 3.35）或被索引/约束引用时 DROP 才会失败；见 docstring 的降级理由
            _log.warning("v60: 删除 %s.%s 失败（%s），保留该列", _TABLE, col, exc)
    _log.info("v60: user_favorites 归档重试死列清理完成（本次删除: %s）", dropped or "无")
