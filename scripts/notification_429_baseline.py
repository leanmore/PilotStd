#!/usr/bin/env python3
"""A-6：按渠道统计通知 429 占比（本地库/验证库通用）。

办公室本地库结果只能称“本地开发库参考”；线上基线须在验证环境跑。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


def summarize(rows) -> dict[str, dict[str, int]]:
    """按渠道聚合 total/failed/429（纯函数，便于单测）。"""
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "failed": 0, "r429": 0})
    for channel, status, error in rows:
        s = stats[str(channel or "unknown")]
        s["total"] += 1
        if str(status) == "failed":
            s["failed"] += 1
        if "429" in str(error or ""):
            s["r429"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    # 入口：读库 → 聚合 → 打印；本地库结果仅作参考
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pilotstd.db")
    args = ap.parse_args(argv)

    db = Path(args.db)
    if not db.exists():
        print(f"[FAIL] db not found: {db}")
        return 1

    conn = sqlite3.connect(db)
    try:
        stats = summarize(conn.execute("SELECT channel, status, error_msg FROM notification_log"))
    finally:
        conn.close()

    print(f"{'CHANNEL':12} {'TOTAL':>6} {'FAILED':>6} {'429':>5} {'429/TOTAL':>9}")
    for ch in sorted(stats):
        s = stats[ch]
        pct = 100.0 * s["r429"] / s["total"] if s["total"] else 0.0
        print(f"{ch:12} {s['total']:6} {s['failed']:6} {s['r429']:5} {pct:8.2f}%")
    print("\n口径：429 按 error_msg 含 '429' 匹配；本结果若来自本地库，仅作“本地开发库参考”。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
