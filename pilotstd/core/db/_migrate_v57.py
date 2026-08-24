# 模块：项目/核心/数据库/迁移_v57脚本
# v57：收藏分类——4 表新增 standard_type 列 + 存量分批回填（批次7）
# 设计依据：docs/designs/favorite-classification-design.md（批次6）
# 枚举值（语义化，批次7 指令）：
#   NationalStd=国家标准 / IndustryStd=行业标准统称桶 / LocalStd=地方标准 / Unknown=推断失败兜底
# 精确映射（实测 source_site 值域，来自 BaseAnnounceCrawler.source_site = f"announcement_{standard_type}"）：
#   announcement_gb → NationalStd, announcement_hb → IndustryStd, announcement_db → LocalStd
# 严禁 LIKE 模糊匹配；严禁强行猜测（推断失败落 Unknown）。
# 幂等性：PRAGMA 检查列存在性，存在即跳过；回填仅处理 standard_type='Unknown' 行。
# Dry-run：--dry-run 参数仅输出预计影响行数，不实际执行。

import logging
import os
import time
from typing import Any

# 精确映射字典（source_site → 语义化枚举），严禁模糊匹配
# 来源：pilotstd.constants.announce_types.SOURCE_SITE_TO_STANDARD_TYPE（SSOT，避免双源漂移）
from pilotstd.constants.announce_types import SOURCE_SITE_TO_STANDARD_TYPE

from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v57")

_SOURCE_SITE_MAP: dict[str, str] = dict(SOURCE_SITE_TO_STANDARD_TYPE)

# 需加列的目标表（批次7：4 张）
_TARGET_TABLES = (
    "announcement_record",
    "user_favorites",
    "favorite_downloads",
    "download_queue",
)
# 各表需补充的列（表 → 列定义列表）：
# - standard_type：4 表统一（收藏分类）
# - user_favorites.standard_number：联合去重 (user_id, standard_number, standard_type) 所需
#   （v31 建表时无此列，生产亦缺——批次7 补上）
_COLUMNS_BY_TABLE: dict[str, list[tuple[str, str]]] = {
    "announcement_record": [("standard_type", "TEXT NOT NULL DEFAULT 'Unknown'")],
    "user_favorites": [
        ("standard_type", "TEXT NOT NULL DEFAULT 'Unknown'"),
        ("standard_number", "TEXT"),
    ],
    "favorite_downloads": [("standard_type", "TEXT NOT NULL DEFAULT 'Unknown'")],
    "download_queue": [("standard_type", "TEXT NOT NULL DEFAULT 'Unknown'")],
}

_CHUNK_SIZE = 1000  # 分批回填 chunk_size（避免长事务锁表）
_SLEEP_SECONDS = 0.1  # 批间节流


def _column_exists(db: Any, table: str, col: str) -> bool:
    """PRAGMA 检查列是否存在（幂等 DDL 前提）。"""
    cols = {r["name"] for r in db.fetchall(f"PRAGMA table_info({table})")}
    return col in cols


def _ensure_columns(db: Any) -> None:
    """幂等补列：缺失才 ALTER，失败带日志抛出（不静默）。"""
    for table in _TARGET_TABLES:
        exists = db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        if not exists:
            _log.info("v57: 表 %s 不存在，跳过补列", table)
            continue
        for col_name, col_def in _COLUMNS_BY_TABLE.get(table, []):
            if _column_exists(db, table, col_name):
                _log.debug("v57: 表 %s 已含列 %s，跳过", table, col_name)
                continue
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                _log.info("v57: 表 %s 补列 %s %s 完成", table, col_name, col_def)
            except Exception:
                _log.exception("v57: 表 %s 补列 %s 失败", table, col_name)
                raise


def _preview_counts(db: Any) -> dict[str, int]:
    """Dry-run：统计各表按标准类型推断的预计行数（不实际写入）。"""
    # Step1：announcement_record 按 source_site 精确映射
    preview: dict[str, int] = {}
    rows = db.fetchall(
        "SELECT source_site, COUNT(*) AS cnt FROM announcement_record GROUP BY source_site"
    )
    for r in rows or []:
        mapped = _SOURCE_SITE_MAP.get(r["source_site"], "Unknown")
        preview[mapped] = preview.get(mapped, 0) + (r["cnt"] or 0)
    return preview


def _backfill_announcement_record(db: Any) -> int:
    """Step2：分批回填 announcement_record（source_site 精确映射 → chunk 更新）。"""
    updated = 0
    while True:
        rows = db.fetchall(
            "SELECT id, source_site FROM announcement_record "
            "WHERE standard_type='Unknown' AND source_site IS NOT NULL LIMIT ?",
            (_CHUNK_SIZE,),
        )
        if not rows:
            break
        for r in rows:
            st = _SOURCE_SITE_MAP.get(r["source_site"], "Unknown")
            db.execute(
                "UPDATE announcement_record SET standard_type=? WHERE id=?", (st, r["id"])
            )
            updated += 1
        # 提交由上层事务边界处理；批间节流
        time.sleep(_SLEEP_SECONDS)
    return updated


def _backfill_favorite_tables(db: Any) -> tuple[int, int, int]:
    """Step3：级联回填收藏三表（经 record_id 关联 announcement_record 取类型）。

    返回 (user_favorites 更新数, favorite_downloads 更新数, download_queue 更新数)。
    download_queue 无 record_id，经 standard_number 关联 announcement_record 匹配。
    """
    uf = fd = dq = 0

    # 3a: user_favorites —— record_id → announcement_record.standard_type
    while True:
        rows = db.fetchall(
            "SELECT uf.id, COALESCE(ar.standard_type, 'Unknown') AS st "
            "FROM user_favorites uf LEFT JOIN announcement_record ar ON uf.record_id = ar.id "
            "WHERE uf.standard_type='Unknown' LIMIT ?",
            (_CHUNK_SIZE,),
        )
        if not rows:
            break
        for r in rows:
            db.execute("UPDATE user_favorites SET standard_type=? WHERE id=?", (r["st"], r["id"]))
            uf += 1
        time.sleep(_SLEEP_SECONDS)

    # 3b: favorite_downloads —— record_id 关联（favorite_downloads 有 record_id）
    while True:
        rows = db.fetchall(
            "SELECT fd.id, COALESCE(ar.standard_type, 'Unknown') AS st "
            "FROM favorite_downloads fd LEFT JOIN announcement_record ar ON fd.record_id = ar.id "
            "WHERE fd.standard_type='Unknown' LIMIT ?",
            (_CHUNK_SIZE,),
        )
        if not rows:
            break
        for r in rows:
            db.execute("UPDATE favorite_downloads SET standard_type=? WHERE id=?", (r["st"], r["id"]))
            fd += 1
        time.sleep(_SLEEP_SECONDS)

    # 3c: download_queue —— standard_number 关联
    while True:
        rows = db.fetchall(
            "SELECT dq.id, COALESCE(ar.standard_type, 'Unknown') AS st "
            "FROM download_queue dq LEFT JOIN announcement_record ar "
            "ON dq.standard_number = ar.standard_number "
            "WHERE dq.standard_type='Unknown' LIMIT ?",
            (_CHUNK_SIZE,),
        )
        if not rows:
            break
        for r in rows:
            db.execute("UPDATE download_queue SET standard_type=? WHERE id=?", (r["st"], r["id"]))
            dq += 1
        time.sleep(_SLEEP_SECONDS)

    return uf, fd, dq


@migration(57)
def _migrate_v57_favorite_standard_type(db: Any) -> None:
    """批次7：4 表补列 + 存量分批回填（幂等、精确映射、禁猜 Unknown）。

    Dry-run 支持：设置环境变量 MIGRATE_DRY_RUN=1 时仅输出预计影响行数，
    不执行任何 DDL/DML（供 staging 预检）。
    """
    if os.environ.get("MIGRATE_DRY_RUN") == "1":
        _log.info("v57: DRY-RUN 模式——仅预览，不执行任何变更")
        total_ar = db.fetchone("SELECT COUNT(*) AS cnt FROM announcement_record")
        ar_total = total_ar["cnt"] if total_ar else 0
        _log.info("v57: DRY-RUN announcement_record 总数=%d", ar_total)
        for st, cnt in sorted(_preview_counts(db).items()):
            _log.info("v57: DRY-RUN 预计 %s: %d 行", st, cnt)
        unknown_pct = 0.0
        if ar_total:
            unknown_pct = _preview_counts(db).get("Unknown", 0) / ar_total * 100
        _log.info("v57: DRY-RUN Unknown 占比=%.2f%%（阈值 10%%）", unknown_pct)
        return

    _ensure_columns(db)

    ar_updated = _backfill_announcement_record(db)
    uf_updated, fd_updated, dq_updated = _backfill_favorite_tables(db)

    _log.info(
        "v57 完成: announcement_record=%d user_favorites=%d favorite_downloads=%d download_queue=%d",
        ar_updated, uf_updated, fd_updated, dq_updated,
    )
