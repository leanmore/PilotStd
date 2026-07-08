#!/usr/bin/env python3
"""公告数据诊断与修复工具（容器内直接执行）

用法（在容器终端内）：
    python /app/docker/diagnose_announce.py          # 仅诊断
    python /app/docker/diagnose_announce.py --fix    # 诊断 + 修复
    python /app/docker/diagnose_announce.py --help   # 帮助
"""

import os
import sqlite3
import sys
from datetime import date

DB_PATH = os.path.join(os.environ.get("DATA_DIR", "/app/data"), "pilotstd.db")


def connect() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def divider(title: str = "") -> None:
    print()
    print("=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def step1_date_distribution(conn: sqlite3.Connection) -> None:
    divider("步骤1 — fetched_at 日期分布 (Top 10)")
    rows = conn.execute(
        "SELECT date(fetched_at) AS fetch_date, COUNT(*) AS n "
        "FROM announcement_record "
        "GROUP BY fetch_date ORDER BY n DESC LIMIT 10"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM announcement_record").fetchone()[0]
    if not rows:
        print("  announcement_record 表为空，无需诊断。")
        return
    for r in rows:
        pct = r["n"] / total * 100 if total else 0
        flag = " ⚠️  异常集中" if pct > 50 else ""
        print(f"  {r['fetch_date']:>12s}  {r['n']:>8d} 行  ({pct:5.1f}%){flag}")
    if rows and rows[0]["n"] / max(total, 1) > 0.5:
        print()
        print("  🔴 结论：超 50% 数据集中在同一天 → 确认全量抓取 Bug")


def step2_duplicates(conn: sqlite3.Connection) -> None:
    divider("步骤2 — 重复记录检查")
    rows = conn.execute(
        "SELECT source_site, pid, standard_number, COUNT(*) AS dup "
        "FROM announcement_record "
        "GROUP BY source_site, pid, standard_number "
        "HAVING COUNT(*) > 1 "
        "ORDER BY dup DESC LIMIT 20"
    ).fetchall()
    if not rows:
        print("  ✅ 无重复记录")
        return
    for r in rows:
        print(f"  {r['source_site']:20s}  pid={r['pid'][:20]:20s}  std={r['standard_number']:24s}  ×{r['dup']}")
    print("  🔴 共发现重复组，需清理")


def step3_stats_comparison(conn: sqlite3.Connection) -> None:
    divider("步骤3 — 统计卡片对照")
    total_all = conn.execute("SELECT COUNT(*) FROM announcement_record").fetchone()[0]
    matched = conn.execute("SELECT COUNT(*) FROM announcement_record WHERE matched=1").fetchone()[0]
    _today = "date('now','localtime')"
    new_all = conn.execute(f"SELECT COUNT(*) FROM announcement_record WHERE date(fetched_at)={_today}").fetchone()[0]
    gb_all = conn.execute("SELECT COUNT(*) FROM announcement_record WHERE source_site='announcement_gb'").fetchone()[0]
    hb_all = conn.execute("SELECT COUNT(*) FROM announcement_record WHERE source_site='announcement_hb'").fetchone()[0]
    db_all = conn.execute("SELECT COUNT(*) FROM announcement_record WHERE source_site='announcement_db'").fetchone()[0]
    new_gb = conn.execute(
        f"SELECT COUNT(*) FROM announcement_record WHERE source_site='announcement_gb' AND date(fetched_at)={_today}"
    ).fetchone()[0]
    new_hb = conn.execute(
        f"SELECT COUNT(*) FROM announcement_record WHERE source_site='announcement_hb' AND date(fetched_at)={_today}"
    ).fetchone()[0]
    new_db = conn.execute(
        f"SELECT COUNT(*) FROM announcement_record WHERE source_site='announcement_db' AND date(fetched_at)={_today}"
    ).fetchone()[0]

    print(f"  {'指标':<12s} {'总计':>8s} {'国标':>8s} {'行标':>8s} {'地标':>8s}")
    print(f"  {'-' * 44}")
    print(f"  {'标准总数':<12s} {total_all:>8d} {gb_all:>8d} {hb_all:>8d} {db_all:>8d}")
    print(f"  {'已匹配':<12s} {matched:>8d}")
    print(f"  {'今日新增':<12s} {new_all:>8d} {new_gb:>8d} {new_hb:>8d} {new_db:>8d}")
    print()

    if total_all > 0 and new_all == total_all:
        print("  🔴 今日新增 = 标准总数 → 确认统计膨胀，数据为同一天全量入库")
    elif new_all > total_all * 0.5:
        print("  🟡 今日新增占比 > 50%，疑似异常")
    else:
        print("  ✅ 统计数据正常")


def step4_fix(conn: sqlite3.Connection) -> None:
    divider("步骤4 — 执行修复")
    print("  将清空以下 4 张表的数据：")
    print("    - announcement_record（公告明细）")
    print("    - announcement_match（匹配缓存，派生数据）")
    print("    - fetch_checkpoint（抓取断点，下次从最新开始）")
    print("    - fetch_task WHERE task_type='announcement'（历史任务）")
    print()
    print("  ⚠️  不会删除：file_index、adapter_health、用户数据等核心表")
    print()

    # 备份
    backup_path = DB_PATH + f".backup_{date.today().strftime('%Y%m%d')}"
    print(f"  正在备份数据库 → {backup_path}")
    bak = sqlite3.connect(backup_path)
    conn.backup(bak)
    bak.close()
    print("  ✅ 备份完成")
    print()

    # 执行清理
    tables = [
        ("announcement_record", "DELETE FROM announcement_record"),
        ("announcement_match", "DELETE FROM announcement_match"),
        ("fetch_checkpoint", "DELETE FROM fetch_checkpoint"),
        ("fetch_task", "DELETE FROM fetch_task WHERE task_type='announcement'"),
    ]
    for name, sql in tables:
        try:
            conn.execute(sql)
            conn.commit()
            remaining = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(f"  ✅ {name}: 已清空（剩余 {remaining} 行）")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    print()
    print("  修复完成。下次定时抓取或手动'立即抓取'将重新获取最新公告。")


def main() -> None:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    do_fix = "--fix" in sys.argv
    conn = connect()

    print(f"📋 数据库: {DB_PATH}")
    print(f"📋 模式: {'诊断 + 修复' if do_fix else '仅诊断'}")

    step1_date_distribution(conn)
    step2_duplicates(conn)
    step3_stats_comparison(conn)

    if do_fix:
        step4_fix(conn)
        # 修复后重新验证
        step3_stats_comparison(conn)
    else:
        divider()
        total = conn.execute("SELECT COUNT(*) FROM announcement_record").fetchone()[0]
        if total > 0:
            today_new = conn.execute(
                "SELECT COUNT(*) FROM announcement_record WHERE date(fetched_at)=date('now','localtime')"
            ).fetchone()[0]
            if today_new == total:
                print("  💡 确认需要修复？重新运行: python /app/docker/diagnose_announce.py --fix")
            else:
                print("  ✅ 数据状态正常，无需修复")
        else:
            print("  ✅ 表为空，无需修复")

    conn.close()


if __name__ == "__main__":
    main()
