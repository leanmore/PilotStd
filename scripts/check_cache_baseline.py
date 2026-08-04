#!/usr/bin/env python
# 模块：scripts/check_cache_baseline.py
# 生成 standard_info_cache 表的完整基线报告
# 用途：CLI 冷启结束后调用，为 WinUI 甲轮一致性校验提供基线
# 用法：python scripts/check_cache_baseline.py [--db data/pilotstd.db]

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))  # 北京时间


def _now() -> str:
    return datetime.now(TZ).isoformat()


def _timestamp() -> str:
    return datetime.now(TZ).strftime("%Y%m%d_%H%M%S")


def generate_baseline(db_path: str, output_dir: str) -> str:
    """生成基线报告，返回输出文件路径。"""
    if not os.path.exists(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}")
        sys.exit(1)

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
        sys.exit(1)

    print("[BASELINE] 正在生成 standard_info_cache 基线报告...")

    rows = conn.execute(
        "SELECT id, standard_number, source_site, cached_at, source FROM standard_info_cache ORDER BY id"
    ).fetchall()

    total = len(rows)
    sources: dict[str, int] = {}
    records: list[dict] = []
    cached_vals: list[str] = []

    for r in rows:
        site = r["source_site"]
        sources[site] = sources.get(site, 0) + 1
        rec = {
            "id": r["id"],
            "standard_number": r["standard_number"],
            "source_site": site,
            "cached_at": r["cached_at"],
            "source": r["source"],
        }
        records.append(rec)
        if r["cached_at"]:
            cached_vals.append(r["cached_at"])

    records_json = json.dumps(records, sort_keys=True, ensure_ascii=False)
    records_hash = hashlib.md5(records_json.encode()).hexdigest()

    baseline = {
        "table": "standard_info_cache",
        "total": total,
        "sources": sources,
        "records": records,
        "time_range": {
            "min": min(cached_vals) if cached_vals else None,
            "max": max(cached_vals) if cached_vals else None,
        },
        "hash": records_hash,
        "generated_at": _now(),
    }

    os.makedirs(output_dir, exist_ok=True)
    filename = f"cache_baseline_{_timestamp()}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)

    conn.close()

    print(f"[BASELINE] 共 {total} 条记录")
    print(f"[BASELINE] 报告已保存: {filepath}")
    return filepath


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="生成 standard_info_cache 基线报告")
    p.add_argument("--db", default=os.path.join("data", "pilotstd.db"), help="SQLite 数据库路径")
    p.add_argument(
        "--output-dir",
        default=os.path.join("tests", ".cache", "baseline"),
        help="输出目录",
    )
    args = p.parse_args()

    generate_baseline(args.db, args.output_dir)
