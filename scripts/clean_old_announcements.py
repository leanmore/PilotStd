#!/usr/bin/env python3
"""清理 publish_date 早于指定日期的公告历史数据。

用法:
    python scripts/clean_old_announcements.py
    python scripts/clean_old_announcements.py --yes          # 跳过确认
    python scripts/clean_old_announcements.py --cutoff 2025-01-01  # 自定义阈值

安全设计:
    - 仅删除 announcement_record 中 publish_date < cutoff 的记录
    - announcement_match 是缓存表（无 publish_date 列），不影响 UI，不动
    - 不动 file_index / users / api_keys 等核心表
    - 执行前打印待删行数 + 要求确认
"""

import os
import sqlite3
import sys

CUTOFF_DEFAULT = "2026-01-01"


def _find_db() -> str:
    """按优先级查找数据库路径。"""
    # 1) 环境变量
    db = os.environ.get("PILOTSTD_DB")
    if db and os.path.exists(db):
        return db

    # 2) DATA_DIR（Docker 兼容）
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        candidate = os.path.join(data_dir, "pilotstd.db")
        if os.path.exists(candidate):
            return candidate

    # 3) 从 pilotstd.core 推导（本地开发）
    try:
        from pilotstd.core.config.paths import get_db_path

        return get_db_path()
    except Exception:
        pass

    print("❌ 找不到数据库。请设置 DATA_DIR 或 PILOTSTD_DB 环境变量。")
    sys.exit(1)


def main() -> None:
    cutoff = CUTOFF_DEFAULT
    auto_yes = False

    for arg in sys.argv[1:]:
        if arg in ("--yes", "-y"):
            auto_yes = True
        elif arg.startswith("--cutoff="):
            cutoff = arg.split("=", 1)[1]
        elif arg == "--cutoff":
            print("用法: --cutoff=YYYY-MM-DD")
            sys.exit(1)

    db_path = _find_db()
    conn = sqlite3.connect(db_path)

    # ── 统计 ──
    total = conn.execute("SELECT COUNT(*) FROM announcement_record").fetchone()[0]
    old = conn.execute(
        "SELECT COUNT(*) FROM announcement_record WHERE publish_date < ? AND publish_date != ''",
        (cutoff,),
    ).fetchone()[0]

    print("=" * 58)
    print("  公告历史数据清洗（按日期过滤）")
    print("=" * 58)
    print(f"  数据库: {db_path}")
    print(f"  清洗阈值: publish_date < {cutoff}")
    print()
    print(f"  announcement_record 总行数: {total:>8,}")
    print(f"  待删除 (publish_date < {cutoff}): {old:>8,}")
    print()

    if old == 0:
        print("✅ 没有早于阈值的记录，无需清洗。")
        conn.close()
        return

    # ── 确认 ──
    if not auto_yes:
        print("⚠️  以上记录将被永久删除。")
        print("   不会影响 file_index / users / api_keys 等核心表。")
        print("-" * 58)
        try:
            answer = input("  确认执行？[y/N] ").strip().lower()
        except EOFError:
            print("\n  未检测到交互终端，使用 --yes 参数跳过确认")
            sys.exit(1)
        if answer not in ("y", "yes"):
            print("  已取消。")
            conn.close()
            sys.exit(0)

    # ── 执行 ──
    print("\n  清理中...")

    conn.execute(
        "DELETE FROM announcement_record WHERE publish_date < ? AND publish_date != ''",
        (cutoff,),
    )
    del_ar = conn.total_changes
    conn.commit()

    remaining = conn.execute("SELECT COUNT(*) FROM announcement_record").fetchone()[0]

    print(f"  announcement_record   -{del_ar:>,} 行")
    print(f"  剩余公告记录:           {remaining:>,} 行")
    print()
    print("=" * 58)
    print("  ✅ 清洗完成。")
    print("=" * 58)

    conn.close()


if __name__ == "__main__":
    main()
