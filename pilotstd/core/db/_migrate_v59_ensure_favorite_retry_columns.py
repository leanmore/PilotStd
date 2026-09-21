# 模块：项目/核心/数据库/迁移_v59脚本
# v59：幂等补全 user_favorites 的归档重试列（archive_retry_count / last_archive_attempt）
# 背景：v36 的补列逻辑（_migrate_v31_plus.py:224-233，逐列 try/except 吞异常）在这台库上
#       未建成这两列；v52 兜底只补了 publish_date；此后 _schema_version 到达版本顶，
#       database.py:144 `current >= target` 直接 early-return —— 重发镜像也不会再执行任何迁移。
#       结果：GET /api/favorites/{record_id}/status 对全部收藏返回 500
#       （sqlite3.OperationalError: no such column: archive_retry_count，2026-09-21 实测）。
# 铁律：已执行迁移源码不可变（P-106，改动会触发 checksum 不匹配导致库无法启动），
#       故不动 v36/v52，新增版本号兜底（同 v48/v50/v52/v56/v57/v58 的 ensure 范式）。
# 幂等性：仅对缺失列执行 ALTER；已存在则零副作用。

import logging
from typing import Any

from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v59")


@migration(59)
def _migrate_v59_ensure_favorite_retry_columns(db: Any) -> None:
    """幂等补全 user_favorites.last_archive_attempt / archive_retry_count。

    两列的读取方是收藏状态接口（docker/api/favorites.py 的 get_favorite_status）；
    缺失即整条 SQL 报错 500。列定义与 v36 目标结构一致（TEXT / INTEGER DEFAULT 0），
    不改变既有语义。
    """
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")}
    if "last_archive_attempt" not in cols:
        db.execute("ALTER TABLE user_favorites ADD COLUMN last_archive_attempt TEXT")
    if "archive_retry_count" not in cols:
        db.execute("ALTER TABLE user_favorites ADD COLUMN archive_retry_count INTEGER DEFAULT 0")
    added = sorted({"archive_retry_count", "last_archive_attempt"} - cols)
    _log.info("v59: user_favorites 归档重试列已确保存在（本次补列: %s）", added or "无")
