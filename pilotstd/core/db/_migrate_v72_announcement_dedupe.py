# 模块：迁移 v72 — 公告标准号归一化 + standard_count 重算（全字段口径）
"""v72：把 `announcement_record.standard_number` 归一化到全项目唯一实现的口径，并重算
`standard_count = 实际行数`。

背景（2026-11-02 实测）：HTML 与 WPS 附件对同一标准常写成 `GB 11887-2026` / `GB 11887—2026`，
入库键原样保留源站写法，UNIQUE(source_site,pid,standard_number,language) 拦不住 ⇒ 同一公告
把 21 项落成 42 行；`standard_count` 又是按解析条目数写入的 42，导致 `/api/announce/reconcile`
长期报 `declared=42 actual=21`。

**去重口径（2026-11-03 修订）**：全字段 100% 一致才允许合并。归一化后撞键但任一字段
（名称/代替号/发布日期/实施日期/语种/外文名…）不同 ⇒ **不合并、不改写、记 WARNING**，
保留两行由人工/重解析处理。去重不得掩盖解析差异。

本迁移只做两件事，且幂等（重复执行第二次 affected=0）：
  1. 把可安全归一化的 `standard_number` 改写为统一写法；撞键且全字段相同时删除重复行，
     撞键但字段不同时保留并告警；
  2. 按 (source_site, announce_no) 重算 `standard_count`。

不整表清空、不动 `announcements` 正文、不改任何历史迁移源码（P-106）。
"""

import logging
import re
from typing import Any

from pilotstd.core.std_utils import normalize_std_code_text as _normalize_code

from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v72")

_CHUNK_SIZE = 1000

# 参与「是否同一条记录」比对的全部解析字段（与 parser._DEDUPE_FIELDS 同口径；
# 迁移是冻结快照，故在此显式列出，避免依赖业务层）。
_FIELDS = (
    "standard_number",
    "std_name",
    "foreign_name",
    "language",
    "superseded_by",
    "publish_date",
    "implement_date",
    "expiry_date",
)

_NAME_TAIL_RE = re.compile(r"\s{2,}\d{4}-\d{2}-\d{2}")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_WS_RE = re.compile(r"\s+")


def _clean_name(name: str) -> str:
    """名称清洗（与 parser._clean_std_name 同口径：去尾部日期/行号、去控制字符）。"""
    text = _NAME_TAIL_RE.split(str(name or ""), maxsplit=1)[0]
    text = _CTRL_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _row_key(row: dict[str, Any]) -> tuple[str, ...]:
    """全字段比较键：任一字段不同即两条不同记录。"""
    out = []
    for field in _FIELDS:
        value = str(row.get(field) or "")
        if field in ("standard_number", "superseded_by"):
            out.append(_normalize_code(value))
        elif field == "std_name":
            out.append(_clean_name(value))
        else:
            out.append(_WS_RE.sub(" ", value).strip())
    return tuple(out)


def _table_exists(db: Any, table: str) -> bool:
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return row is not None


def _normalize_existing_codes(db: Any) -> tuple[int, int, int]:
    """归一化历史标准号：全字段相同才删重复；字段不同保留并告警。

    返回 (改写数, 合并删除数, 冲突保留数)。写操作按批 `executemany` 提交
    （逐行 execute 每行一次 commit，21 万行会到分钟级）。
    """
    updated = 0
    merged = 0
    conflicts = 0
    planned: dict[tuple[str, str, str, str], tuple[int, tuple[str, ...]]] = {}
    last_id = 0
    while True:
        rows = db.fetchall(
            "SELECT id, source_site, pid, standard_number, language, std_name,"
            " foreign_name, superseded_by, publish_date, implement_date, expiry_date"
            " FROM announcement_record WHERE id > ? ORDER BY id LIMIT ?",
            (last_id, _CHUNK_SIZE),
        )
        if not rows:
            break
        updates: list[tuple[str, int]] = []
        deletes: list[tuple[int]] = []
        for r in rows:
            last_id = r["id"]
            raw = str(r["standard_number"] or "")
            normalized = _normalize_code(raw)
            if normalized == raw:
                continue
            key = (str(r["source_site"]), str(r["pid"]), normalized, str(r["language"] or ""))
            candidate = dict(r)
            candidate["standard_number"] = normalized
            row_key = _row_key(candidate)

            keep = planned.get(key)
            if keep is None:
                target = db.fetchone(
                    "SELECT id, source_site, pid, standard_number, language, std_name,"
                    " foreign_name, superseded_by, publish_date, implement_date, expiry_date"
                    " FROM announcement_record"
                    " WHERE source_site=? AND pid=? AND standard_number=?"
                    "   AND COALESCE(language,'')=COALESCE(?,'') AND id<>? LIMIT 1",
                    (r["source_site"], r["pid"], normalized, r["language"], r["id"]),
                )
                if target is not None:
                    keep = (int(target["id"]), _row_key(target))
                else:
                    planned[key] = (r["id"], row_key)
                    updates.append((normalized, r["id"]))
                    continue
            if keep[1] == row_key:
                # 全字段一致 → 真重复，删除本行（保留 keep）
                deletes.append((r["id"],))
            else:
                # 字段有差异 → 严禁合并；保留原写法并告警，等人工/重解析处理
                conflicts += 1
                _log.warning(
                    "v72: 归一化后撞键但字段不同，保留两行 id=%s / id=%s number=%s",  # i18n-allow: 迁移日志
                    keep[0],
                    r["id"],
                    normalized,
                )

        if updates:
            db.executemany(
                "UPDATE announcement_record SET standard_number=? WHERE id=?", updates
            )
        if deletes:
            db.executemany("DELETE FROM announcement_record WHERE id=?", deletes)
        updated += len(updates)
        merged += len(deletes)
    return updated, merged, conflicts


def _recompute_standard_counts(db: Any) -> int:
    """按 (source_site, announce_no) 重算 standard_count = 该公告实际行数。

    用临时表把「声明值 vs 实际值」的差异行一次算出来，避免逐公告全表扫描。
    """
    db.execute("DROP TABLE IF EXISTS _v72_counts")
    db.execute(
        "CREATE TEMP TABLE _v72_counts AS"
        " SELECT source_site, TRIM(announce_no) AS announce_no, COUNT(*) AS actual"
        " FROM announcement_record"
        " WHERE announce_no IS NOT NULL AND TRIM(announce_no) <> ''"
        " GROUP BY source_site, TRIM(announce_no)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS _v72_counts_key ON _v72_counts(source_site, announce_no)")
    cur = db.execute(
        "UPDATE announcement_record SET standard_count = ("
        "  SELECT c.actual FROM _v72_counts c"
        "  WHERE c.source_site = announcement_record.source_site"
        "    AND c.announce_no = TRIM(announcement_record.announce_no))"
        " WHERE announce_no IS NOT NULL AND TRIM(announce_no) <> ''"
        "   AND EXISTS (SELECT 1 FROM _v72_counts c"
        "     WHERE c.source_site = announcement_record.source_site"
        "       AND c.announce_no = TRIM(announcement_record.announce_no)"
        "       AND c.actual <> COALESCE(announcement_record.standard_count, -1))"
    )
    changed = int(cur.rowcount or 0)
    db.execute("DROP TABLE IF EXISTS _v72_counts")
    return changed


@migration(72)
def _migrate_v72_announcement_dedupe(db: Any) -> None:
    """公告标准号归一化 + standard_count 重算（全字段口径、幂等）。"""
    if not _table_exists(db, "announcement_record"):
        _log.info("v72: announcement_record 不存在，跳过")  # i18n-allow: 迁移日志
        return

    normalized, merged, conflicts = _normalize_existing_codes(db)
    count_changed = _recompute_standard_counts(db)

    _log.info(
        "v72 完成: 归一化=%d 全字段重复删除=%d 冲突保留=%d standard_count 修正=%d",  # i18n-allow: 迁移日志
        normalized,
        merged,
        conflicts,
        count_changed,
    )
