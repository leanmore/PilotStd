#!/usr/bin/env python3
"""P2-11 one-off repair for malformed ``standard_validity`` keys (dry-run by default).

Background (remote backup measured 2026-11-13, 819 validity rows):
- 7 keys are ``" <number>-<year>"`` (leading space, missing logical code);
- 5 of them (TSG 11-2020 / 23-2021 / 7-2019 / 8001-2019 / 8002-2022) have both a main
  regulation row (``TSG``) and amendment rows (``T/SG`` whose ``std_name`` contains
  ``修改单``) in ``file_index`` => excluding amendments leaves exactly one code, and the
  canonical ``TSG ...`` key already exists => merge into it;
- 2 of them (19001-2020, 47008-1947) have no same-number/year evidence => manual_required.

Rules:
1. only keys matching ``^\\s+(\\d+)(?:\\.(\\d+))?-(\\d{4})$`` are considered;
2. candidates = distinct ``logical_code`` from ``file_index`` by (number, year[, part]);
3. candidates whose rows are all amendments (``修改单``) are dropped;
4. exactly one code left => canonical key ``CODE number[.part]-year``; merge if it exists,
   otherwise rename;
5. everything else is reported as ``manual_required`` and left untouched;
6. idempotent: repaired keys no longer match the malformed pattern.

Usage:
  python scripts/repair_validity_keys_v2.py --db data/pilotstd.db              # dry-run
  python scripts/repair_validity_keys_v2.py --db data/pilotstd.db --apply     # backup + write
  python scripts/repair_validity_keys_v2.py --db ... --json C:/Temp/plan.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# 畸形键：前导空白 + 顺序号[.部分号]-年份（v74 正则同口径）
MALFORMED_RE = re.compile(r"^\s+(\d+)(?:\.(\d+))?-(\d{4})$")
# file_index 里改单/修改单类文件不是独立标准，不能拿它的代号做规范键
AMENDMENT_MARK = "修改单"


@dataclass
class Repair:
    """一条待执行的修复动作（plan 阶段的纯数据）。"""

    malformed: str
    canonical: str = ""
    action: str = ""  # merge | rename | manual_required
    reason: str = ""
    row_id: int | None = None
    canonical_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _connect(db_path: str) -> sqlite3.Connection:
    """Open the SQLite database read/write (caller decides whether to write)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _canonical_candidates(conn: sqlite3.Connection, number: int, year: int, part: int | None) -> dict[str, list[str]]:
    """Return {logical_code: [std_name, ...]} for the given number/year[/part]."""
    # 只有带分部的畸形键才按 part 过滤；不带分部的用 number+year 全量候选
    sql = "SELECT logical_code, part, std_name FROM file_index WHERE number=? AND year=?"
    params: list[Any] = [number, year]
    if part is not None:
        sql += " AND part=?"
        params.append(part)
    result: dict[str, list[str]] = {}
    for row in conn.execute(sql, tuple(params)):
        code = str(row["logical_code"] or "")
        if code:
            result.setdefault(code, []).append(str(row["std_name"] or ""))
    return result


def _is_amendment_only(names: list[str]) -> bool:
    """True when every file row for a code is an amendment (``修改单``)."""
    return bool(names) and all(AMENDMENT_MARK in name for name in names)


def _build_canonical(code: str, number: int, part: int | None, year: int) -> str:
    """规范键：`CODE number[.part]-year`（与 v74 的格式完全一致）。"""
    suffix = f".{part}" if part and part > 0 else ""
    return f"{code} {number}{suffix}-{year}"


def plan_repairs(conn: sqlite3.Connection) -> list[Repair]:
    """Compute repair actions without writing anything."""
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row  # 调用方可能用默认 tuple 工厂
    if not _table_exists(conn, "standard_validity"):
        raise SystemExit("standard_validity table not found")
    rows = conn.execute("SELECT * FROM standard_validity ORDER BY id").fetchall()
    existing = {str(r["standard_number"]): r for r in rows}
    repairs: list[Repair] = []
    for row in rows:
        key = str(row["standard_number"] or "")
        match = MALFORMED_RE.match(key)
        if not match:
            continue
        number = int(match.group(1))
        part = int(match.group(2)) if match.group(2) else None
        year = int(match.group(3))
        candidates = _canonical_candidates(conn, number, year, part)
        if not candidates:
            repairs.append(Repair(key, action="manual_required", reason="no file_index evidence", row_id=row["id"]))
            continue
        main_codes = {code: names for code, names in candidates.items() if not _is_amendment_only(names)}
        if len(main_codes) != 1:
            repairs.append(
                Repair(
                    key,
                    action="manual_required",
                    reason=f"ambiguous main codes: {sorted(main_codes) or sorted(candidates)}",
                    row_id=row["id"],
                )
            )
            continue
        code = next(iter(main_codes))
        canonical = _build_canonical(code, number, part, year)
        target = existing.get(canonical)
        if target is not None and int(target["id"]) != int(row["id"]):
            repairs.append(
                Repair(
                    key,
                    canonical=canonical,
                    action="merge",
                    reason=f"canonical exists (id={target['id']})",
                    row_id=row["id"],
                    canonical_id=target["id"],
                )
            )
        elif target is not None:
            repairs.append(
                Repair(key, canonical=canonical, action="rename", reason="already canonical key", row_id=row["id"])
            )
        else:
            repairs.append(
                Repair(key, canonical=canonical, action="rename", reason="unique main code", row_id=row["id"])
            )
    return repairs


def _known(status: str | None) -> bool:
    """状态是否已知：未知/空不算已知，合并时让位给已知状态。"""
    return bool(status) and status != "未知"


def _merge(conn: sqlite3.Connection, malformed: sqlite3.Row, canonical: sqlite3.Row) -> None:
    """Merge malformed row into canonical (status/time/count take the 'better' value)."""
    status = canonical["status"]
    if _known(malformed["status"]) and not _known(canonical["status"]):
        status = malformed["status"]
    last_checked = max(
        str(canonical["last_checked_at"] or ""), str(malformed["last_checked_at"] or "")
    ) or None
    check_count = max(int(canonical["check_count"] or 0), int(malformed["check_count"] or 0))
    created_at = min(
        str(canonical["created_at"] or ""), str(malformed["created_at"] or "")
    ) or None
    updated_at = max(
        str(canonical["updated_at"] or ""), str(malformed["updated_at"] or "")
    ) or None
    last_accessed = max(
        str(canonical["last_accessed_at"] or ""), str(malformed["last_accessed_at"] or "")
    ) or None
    conn.execute(
        "UPDATE standard_validity SET status=?, last_checked_at=?, check_count=?, "
        "created_at=?, updated_at=?, last_accessed_at=? WHERE id=?",
        (status, last_checked, check_count, created_at, updated_at, last_accessed, canonical["id"]),
    )
    conn.execute("DELETE FROM standard_validity WHERE id=?", (malformed["id"],))


def apply_repairs(conn: sqlite3.Connection, repairs: list[Repair]) -> dict[str, int]:
    """Apply merge/rename actions; manual_required rows are never touched."""
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    counts = {"merge": 0, "rename": 0, "manual_required": 0}
    for item in repairs:
        counts[item.action] = counts.get(item.action, 0) + 1
        if item.action == "manual_required":
            continue
        malformed = conn.execute("SELECT * FROM standard_validity WHERE id=?", (item.row_id,)).fetchone()
        if malformed is None:
            continue
        if item.action == "rename":
            conn.execute(
                "UPDATE standard_validity SET standard_number=? WHERE id=?",
                (item.canonical, item.row_id),
            )
            continue
        canonical = conn.execute(
            "SELECT * FROM standard_validity WHERE id=?", (item.canonical_id,)
        ).fetchone()
        if canonical is not None:
            _merge(conn, malformed, canonical)
    conn.commit()
    return counts


def _backup(db_path: str) -> str:
    """Copy the database next to itself; refuse to continue if the copy fails."""
    # 备份与源库同目录：还原时路径最短，且不会跨盘拷贝失败
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = f"{db_path}.bak-{stamp}"
    shutil.copy2(db_path, target)
    return target


def _print_plan(repairs: list[Repair]) -> None:
    """Print one line per planned action plus a summary (human review artifact)."""
    # 先逐条打印，便于运维在窗口前核对每一条的落点
    for item in repairs:
        print(f"[{item.action}] {item.malformed!r} -> {item.canonical!r} ({item.reason})")
    counts: dict[str, int] = {}
    for item in repairs:
        counts[item.action] = counts.get(item.action, 0) + 1
    print(f"summary: {counts}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry: plan first, write only with ``--apply`` (and only after a backup)."""
    parser = argparse.ArgumentParser(description="P2-11 validity key repair (dry-run default)")
    parser.add_argument("--db", required=True, help="path to pilotstd.db (explicit, no default)")
    parser.add_argument("--apply", action="store_true", help="backup then write (default: dry-run)")
    parser.add_argument("--json", dest="json_path", help="write the plan as JSON")
    args = parser.parse_args(argv)

    # --db 必填且要求真实路径：避免误把生产库当成默认参数
    db_path = str(Path(args.db).expanduser().resolve())
    if not Path(db_path).exists():
        print(f"db not found: {db_path}", file=sys.stderr)
        return 2
    conn = _connect(db_path)
    try:
        repairs = plan_repairs(conn)
        _print_plan(repairs)
        if args.json_path:
            Path(args.json_path).write_text(
                json.dumps([item.__dict__ for item in repairs], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if not args.apply:
            print("dry-run only; re-run with --apply to write")
            return 0
        if not any(item.action in ("merge", "rename") for item in repairs):
            print("nothing to apply")
            return 0
        # 写库前必须成功复制备份；备份失败直接抛错终止
        backup = _backup(db_path)
        print(f"backup: {backup}")
        counts = apply_repairs(conn, repairs)
        print(f"applied: {counts}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
