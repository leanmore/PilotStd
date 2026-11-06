# 模块：项目/核心/数据库/迁移_v73脚本
"""v73：把历史表中的裸时间字符串规范为 ISO 8601 带时区偏移量。

历史写入混用 `datetime.now().isoformat()`（本地、无偏移）与 SQLite `CURRENT_TIMESTAMP`
（UTC、空格分隔），导致 retention 比较、跨时区展示不一致。本迁移只做**字符串规范化**：
  - `YYYY-MM-DD HH:MM:SS` → `YYYY-MM-DDTHH:MM:SS+08:00`（按系统本地时区）
  - `YYYY-MM-DDTHH:MM:SS`（无偏移）→ 追加偏移
  - `YYYY-MM-DD` → 当日 00:00:00 + 偏移
已有偏移（`+08:00`/`Z`）的行保持不变；不可解析的行原样保留（人工排查）。
"""

import logging
from datetime import datetime
from typing import Any

from pilotstd.core.time_utils import local_tz

from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v73")


def _offset() -> str:
    off = datetime.now(local_tz()).utcoffset()
    if off is None:
        return "+00:00"
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


@migration(73)
def _migrate_v73_normalize_timestamps(db: Any) -> None:
    """规范化所有表 `*_at` TEXT 列的历史时间字符串。"""
    offset = _offset()
    tables = [
        r["name"]
        for r in db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    updated = 0
    for table in tables:
        cols = [r["name"] for r in db.fetchall(f"PRAGMA table_info({table})")]
        for col in cols:
            if not (col.endswith("_at") or col == "timestamp"):
                continue
            try:
                # 空格分隔（SQLite CURRENT_TIMESTAMP 或旧 isoformat）
                cur = db.execute(
                    f"UPDATE {table} SET {col} = replace({col}, ' ', 'T') || ? "
                    f"WHERE {col} GLOB '????-??-?? ??:??:??'",
                    (offset,),
                )
                updated += cur.rowcount or 0
                # T 分隔但无偏移
                cur = db.execute(
                    f"UPDATE {table} SET {col} = {col} || ? "
                    f"WHERE {col} GLOB '????-??-??T??:??:??'",
                    (offset,),
                )
                updated += cur.rowcount or 0
                # 仅日期
                cur = db.execute(
                    f"UPDATE {table} SET {col} = {col} || 'T00:00:00' || ? "
                    f"WHERE {col} GLOB '????-??-??'",
                    (offset,),
                )
                updated += cur.rowcount or 0
            except Exception:
                # i18n-allow: 内部日志
                _log.exception("v73 规范化 %s.%s 失败", table, col)
                raise
    _log.info("v73 时间规范化完成：%d 行（offset=%s）", updated, offset)  # i18n-allow
