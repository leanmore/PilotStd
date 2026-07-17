#!/usr/bin/env python3
"""清理公告抓取脏数据 — 在 Docker 容器内执行。

用法:
    docker exec -it pilotstd python cleanup_announcement_data.py
    docker exec -it pilotstd python cleanup_announcement_data.py --yes   # 跳过确认

安全设计:
    - 只清 4 张表：announcement_record / announcement_match / fetch_checkpoint / fetch_task
    - 不动 file_index / standard_validity / users / api_keys 等核心表
    - 执行前打印当前行数 + 要求确认
"""

import os
import sqlite3
import sys

# ── 找数据库 ────────────────────────────────────────────────
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
DB_PATH = os.path.join(DATA_DIR, "pilotstd.db")

if not os.path.exists(DB_PATH):
    print(f"❌ 数据库不存在: {DB_PATH}")
    print("   请确认 DATA_DIR 环境变量或容器挂载是否正确")
    sys.exit(1)

AUTO_YES = "--yes" in sys.argv or "-y" in sys.argv

conn = sqlite3.connect(DB_PATH)


def query_count(sql: str) -> int:
    """执行 SQL 查询并返回第一列的整数值。"""
    row = conn.execute(sql).fetchone()
    return int(row[0]) if row else 0


# ── 读当前数据量 ────────────────────────────────────────────
total = query_count("SELECT COUNT(*) FROM announcement_record")
matched = query_count("SELECT COUNT(*) FROM announcement_record WHERE matched = 1")
gb = query_count("SELECT COUNT(*) FROM announcement_record WHERE source_site = 'announcement_gb'")
hb = query_count("SELECT COUNT(*) FROM announcement_record WHERE source_site = 'announcement_hb'")
db = query_count("SELECT COUNT(*) FROM announcement_record WHERE source_site = 'announcement_db'")
am_cnt = query_count("SELECT COUNT(*) FROM announcement_match")
fc_cnt = query_count("SELECT COUNT(*) FROM fetch_checkpoint")
ft_cnt = query_count("SELECT COUNT(*) FROM fetch_task WHERE task_type = 'announcement'")

PROTECTED = "file_index / standard_validity / users / api_keys / adapter_health"

print("=" * 58)
print("  公告脏数据清理工具")
print("=" * 58)
print(f"  数据库: {DB_PATH}")
print()
print(f"  announcement_record   {total:>8,} 行  (gb={gb:,} hb={hb:,} db={db:,} matched={matched:,})")
print(f"  announcement_match    {am_cnt:>8,} 行")
print(f"  fetch_checkpoint      {fc_cnt:>8,} 行")
print(f"  fetch_task(公告)      {ft_cnt:>8,} 行")
print()
print(f"  \N{LOCK} 以下表不会触碰: {PROTECTED}")
print()

if total == 0:
    print("\N{CHECK MARK}  announcement_record 已为空，无需清理。")
    conn.close()
    sys.exit(0)

# ── 确认 ────────────────────────────────────────────────────
if not AUTO_YES:
    print("=" * 58)
    print("  \N{WARNING SIGN}  将删除以上 4 张表的所有数据！")
    print("  已匹配数据清空后，重新抓取会自动重建。")
    print("  file_index（本地标准索引）不受影响。")
    print("=" * 58)
    try:
        answer = input("  确认执行？[y/N] ").strip().lower()
    except EOFError:
        print("\n  未检测到交互终端，使用 --yes 参数跳过确认")
        sys.exit(1)
    if answer not in ("y", "yes"):
        print("  已取消。")
        conn.close()
        sys.exit(0)

# ── 执行 ────────────────────────────────────────────────────
print()
print("  清理中...")

conn.execute("DELETE FROM announcement_record")
del_ar = conn.total_changes

conn.execute("DELETE FROM announcement_match")
del_am = conn.total_changes - del_ar

conn.execute("DELETE FROM fetch_checkpoint")
del_fc = conn.total_changes - del_ar - del_am

conn.execute("DELETE FROM fetch_task WHERE task_type = 'announcement'")
del_ft = conn.total_changes - del_ar - del_am - del_fc

conn.commit()

print(f"  announcement_record   -{del_ar:>,} 行")
print(f"  announcement_match    -{del_am:>,} 行")
print(f"  fetch_checkpoint      -{del_fc:>,} 行")
print(f"  fetch_task(公告)      -{del_ft:>,} 行")
print()
print("=" * 58)
print("  \N{CHECK MARK} 清理完成。")
print("  下次启动服务后统计数据将归零，重新抓取后逐步恢复。")
print("=" * 58)

conn.close()
