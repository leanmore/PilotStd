# 模块：迁移 v74 — 修复 standard_validity 的前导空格/缺代号键
"""v74：把 `standard_validity` 中 `' <number>-<year>'` 形态的畸形键修复为规范键。

背景（2026-11-07 只读核对 prebatch.bak）：
- 803 条中 709 条为畸形键；
- 706 条可由 `file_index` 的 `(number, year[, part])` 唯一还原；
- 1 条与已存在的规范键冲突（合并）；
- 3 条无法还原（保留，人工处理）。

安全约束：
- 只修复能由 file_index 唯一确定 logical_code 的行；
- 多代号/多分部无法唯一确定时不动，记 warning；
- 冲突行按“非未知状态、较新检查时间、max check_count、min created_at”合并；
- 幂等：修复后不再匹配畸形正则，第二次 affected=0。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pilotstd.core.status import Status

from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v74")

_TABLE = "standard_validity"
_MALFORMED_RE = re.compile(r"^\s+(\d+)(?:\.(\d+))?-(\d{4})$")


def _table_exists(db: Any, table: str) -> bool:
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return row is not None


def _ensure_columns(db: Any) -> None:
    """旧库可能还没有 last_changed_at；补列后继续。"""
    cols = {r["name"] for r in db.fetchall(f"PRAGMA table_info({_TABLE})")}
    if "last_changed_at" not in cols:
        db.execute(f"ALTER TABLE {_TABLE} ADD COLUMN last_changed_at TEXT")


def _canonical_key(db: Any, number: int, year: int, part: int | None) -> str | None:
    """用 file_index 还原规范键；无法唯一确定返回 None。"""
    if not _table_exists(db, "file_index"):
        return None
    sql = "SELECT logical_code, part FROM file_index WHERE number=? AND year=?"
    params: list[Any] = [number, year]
    if part is not None:
        sql += " AND part=?"
        params.append(part)
    rows = db.fetchall(sql, tuple(params))
    codes = {str(r.get("logical_code") or "") for r in rows if r.get("logical_code")}
    if len(codes) != 1:
        return None
    code = next(iter(codes))
    parts = {int(r.get("part") or -1) for r in rows}
    if part is None:
        if len(parts) > 1:
            return None
        part = next(iter(parts)) if parts else -1
    suffix = f".{part}" if part and part > 0 else ""
    return f"{code} {number}{suffix}-{year}"


def _known(status: str | None) -> bool:
    return bool(status) and status != Status.UNKNOWN.value


def _max_str(*values: Any) -> str:
    return max((str(v) for v in values if v), default="")


def _min_str(*values: Any) -> str:
    return min((str(v) for v in values if v), default="")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        _log.warning("v74 非法整数，按 0 处理: %r", value)  # i18n-allow: 内部迁移日志
        return 0


def _choose_status(canonical: dict[str, Any], malformed: dict[str, Any]) -> str:
    c, m = canonical.get("status"), malformed.get("status")
    if _known(c) and not _known(m):
        return str(c)
    if _known(m) and not _known(c):
        return str(m)
    if _known(c) and _known(m) and c != m:
        # 以较新检查时间为准；仍相同则保留规范行，并留 warning
        c_time = str(canonical.get("last_checked_at") or "")
        m_time = str(malformed.get("last_checked_at") or "")
        if m_time > c_time:
            _log.warning(
                "v74 状态冲突，采用畸形行: %s / %s (%s vs %s)",  # i18n-allow: 内部迁移日志
                canonical.get("standard_number"),
                malformed.get("standard_number"),
                c,
                m,
            )
            return str(m)
        _log.warning(
            "v74 状态冲突，保留规范行: %s (%s vs %s)",  # i18n-allow: 内部迁移日志
            canonical.get("standard_number"),
            c,
            m,
        )
        return str(c)
    return str(c or m or Status.UNKNOWN.value)


def _merge_into(db: Any, canonical: dict[str, Any], malformed: dict[str, Any]) -> None:
    """把畸形行合并到规范行，再删除畸形行。"""
    later = canonical
    if str(malformed.get("last_checked_at") or "") > str(canonical.get("last_checked_at") or ""):
        later = malformed

    status = _choose_status(canonical, malformed)
    last_checked = _max_str(canonical.get("last_checked_at"), malformed.get("last_checked_at"))
    next_check = str(later.get("next_check_at") or "") or _min_str(
        canonical.get("next_check_at"), malformed.get("next_check_at")
    )
    last_status = str(later.get("last_status") or canonical.get("last_status") or malformed.get("last_status") or "")
    last_status_updated = _max_str(
        canonical.get("last_status_updated_at"), malformed.get("last_status_updated_at")
    )
    last_changed = _max_str(canonical.get("last_changed_at"), malformed.get("last_changed_at"))
    check_count = max(_int(canonical.get("check_count")), _int(malformed.get("check_count")))
    created_at = _min_str(canonical.get("created_at"), malformed.get("created_at"))
    updated_at = _max_str(canonical.get("updated_at"), malformed.get("updated_at"))
    last_accessed = _max_str(canonical.get("last_accessed_at"), malformed.get("last_accessed_at"))
    source_version = str(canonical.get("source_version") or malformed.get("source_version") or "")
    data_state = "fresh" if "fresh" in {
        str(canonical.get("data_state") or ""),
        str(malformed.get("data_state") or ""),
    } else "stale"

    db.execute(
        f"UPDATE {_TABLE} SET status=?, last_checked_at=?, next_check_at=?, "
        "last_status=?, last_status_updated_at=?, last_changed_at=?, "
        "check_count=?, created_at=?, updated_at=?, last_accessed_at=?, "
        "source_version=?, data_state=? WHERE id=?",
        (
            status,
            last_checked or None,
            next_check or None,
            last_status or None,
            last_status_updated or None,
            last_changed or None,
            check_count,
            created_at or None,
            updated_at or None,
            last_accessed or None,
            source_version,
            data_state,
            canonical["id"],
        ),
    )
    db.execute(f"DELETE FROM {_TABLE} WHERE id=?", (malformed["id"],))


@migration(74)
def _migrate_v74_repair_validity_keys(db: Any) -> None:
    """修复畸形 validity 键；幂等。"""
    if not _table_exists(db, _TABLE):
        return
    _ensure_columns(db)

    rows = db.fetchall(f"SELECT * FROM {_TABLE} ORDER BY id")
    malformed_rows = [r for r in rows if _MALFORMED_RE.match(str(r.get("standard_number") or ""))]
    if not malformed_rows:
        return

    existing = {str(r.get("standard_number") or ""): r for r in rows}
    renamed = merged = unresolved = ambiguous = 0

    for row in malformed_rows:
        match = _MALFORMED_RE.match(str(row.get("standard_number") or ""))
        if not match:
            unresolved += 1
            continue
        number = int(match.group(1))
        part = int(match.group(2)) if match.group(2) else None
        year = int(match.group(3))
        canonical_key = _canonical_key(db, number, year, part)
        if not canonical_key:
            unresolved += 1
            _log.warning("v74 无法唯一还原，保留: %r", row.get("standard_number"))  # i18n-allow: 内部迁移日志
            continue

        target = existing.get(canonical_key)
        if target and int(target["id"]) != int(row["id"]):
            _merge_into(db, target, row)
            merged += 1
        else:
            db.execute(
                f"UPDATE {_TABLE} SET standard_number=? WHERE id=?",
                (canonical_key, row["id"]),
            )
            renamed += 1

    _log.info(
        "v74 validity 键修复完成: renamed=%d merged=%d unresolved=%d ambiguous=%d",  # i18n-allow: 内部迁移日志
        renamed,
        merged,
        unresolved,
        ambiguous,
    )
