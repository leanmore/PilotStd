#!/usr/bin/env python
# scripts/check_cache_consistency.py
# 对比 standard_info_cache 当前状态与最新基线报告
# 用途：WinUI 甲轮开始前调用，校验缓存环境未被污染
# 用法：python scripts/check_cache_consistency.py [--db data/pilotstd.db]

import glob
import json
import os
import sqlite3
import sys


def _latest_baseline(baseline_dir: str) -> str | None:
    """返回最新基线报告的路径。"""
    pattern = os.path.join(baseline_dir, "cache_baseline_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def check_consistency(db_path: str, baseline_dir: str) -> dict:
    """对比当前表与基线报告，返回结果 dict。退出码 0=一致, 1=不一致, 2=无基线, 3=DB错误。"""
    baseline_path = _latest_baseline(baseline_dir)
    if not baseline_path:
        print(f"[ERROR] 无基线报告（{baseline_dir}/cache_baseline_*.json）")
        sys.exit(2)

    try:
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] 基线报告读取失败: {e}")
        sys.exit(2)

    if not os.path.exists(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}")
        sys.exit(3)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='standard_info_cache'"
        ).fetchall()
    ]
    if not tables:
        print("[ERROR] standard_info_cache 表不存在")
        conn.close()
        sys.exit(3)

    rows = conn.execute(
        "SELECT id, standard_number, source_site, cached_at, source FROM standard_info_cache ORDER BY id"
    ).fetchall()
    conn.close()

    total = len(rows)
    sources: dict[str, int] = {}
    current_records: dict[int, dict] = {}

    for r in rows:
        site = r["source_site"]
        sources[site] = sources.get(site, 0) + 1
        current_records[r["id"]] = {
            "id": r["id"],
            "standard_number": r["standard_number"],
            "source_site": site,
            "cached_at": r["cached_at"],
            "source": r["source"],
        }

    baseline_records: dict[int, dict] = {}
    for rec in baseline.get("records", []):
        baseline_records[rec["id"]] = rec

    bl_total = baseline.get("total", 0)
    bl_sources = baseline.get("sources", {})
    bl_filename = os.path.basename(baseline_path)

    # 逐项对比
    diff_added: list[dict] = []
    diff_removed: list[dict] = []
    diff_modified: list[dict] = []

    for rid, rec in current_records.items():
        if rid not in baseline_records:
            diff_added.append(rec)

    for rid, rec in baseline_records.items():
        if rid not in current_records:
            diff_removed.append(rec)
        else:
            cur = current_records[rid]
            for field in ("standard_number", "source_site", "cached_at", "source"):
                if cur.get(field) != rec.get(field):
                    diff_modified.append(
                        {
                            "id": rid,
                            "field": field,
                            "baseline": rec.get(field),
                            "current": cur.get(field),
                        }
                    )

    has_diff = total != bl_total or sources != bl_sources or diff_added or diff_removed or diff_modified

    if not has_diff:
        result = {
            "status": "PASS",
            "message": "缓存一致性校验通过",
            "baseline": bl_filename,
            "total": total,
            "sources": sources,
        }
        print(f"[PASS] 缓存一致性校验通过 ({bl_filename})")
        print(f"   总记录: {total}, 来源分布: {sources}")
        sys.exit(0)
    else:
        diff_msg_parts = []
        if diff_added:
            diff_msg_parts.append(f"新增 {len(diff_added)} 条")
        if diff_removed:
            diff_msg_parts.append(f"删除 {len(diff_removed)} 条")
        if diff_modified:
            diff_msg_parts.append(f"修改 {len(diff_modified)} 条")
        diff_msg = ", ".join(diff_msg_parts) if diff_msg_parts else "记录数不一致"

        result = {
            "status": "FAIL",
            "message": f"缓存一致性校验失败: {diff_msg}",
            "baseline": bl_filename,
            "baseline_total": bl_total,
            "current_total": total,
            "baseline_sources": bl_sources,
            "current_sources": sources,
            "diff": {
                "added": diff_added,
                "removed": diff_removed,
                "modified": diff_modified,
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="校验 standard_info_cache 一致性")
    p.add_argument("--db", default=os.path.join("data", "pilotstd.db"), help="SQLite 数据库路径")
    p.add_argument(
        "--baseline-dir",
        default=os.path.join("tests", ".cache", "baseline"),
        help="基线报告目录",
    )
    args = p.parse_args()

    check_consistency(args.db, args.baseline_dir)
