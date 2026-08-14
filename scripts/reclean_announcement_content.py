#!/usr/bin/env python3
"""
scripts/reclean_announcement_content.py — 历史公告正文重新分类

旧版 _HEADING_LINES 只识别 "公告" 和 "备案月报"，导致 "中华人民共和国国家标准"、
"行业标准公告"、"2026年第31号" 等标题行被错误分类为 announce-body，前端 v-html
渲染后不居中。修复 _HEADING_LINES + 新增 _ISSUE_NO_PATTERN 后，需对存量数据
重新执行 clean_announcement_content() 使分类结果同步。

执行方式：
  python scripts/reclean_announcement_content.py --dry-run   # 预览
  python scripts/reclean_announcement_content.py             # 执行更新
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

from pilotstd.announcement._content_cleaner import clean_announcement_content
from pilotstd.core.config.paths import get_db_path


def strip_html_tags(html: str) -> str:
    """Extract plain text from <p class=\"xxx\">text</p>, preserving paragraph separation."""
    if not html:
        return ""
    # 重建原始纯文本：每个 <p> 原本是一个段落，由空行分隔（extract_content 使用 "\n\n".join）。
    # 用双换行拼接，使 clean_announcement_content 正确按段落分割并分类。
    texts = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
    return "\n\n".join(t.strip() for t in texts if t.strip())


def main():
    """Parse args, read announcements, re-clean content, report changes."""
    # 连接数据库，获取所有带内容的公告
    parser = argparse.ArgumentParser(description="Re-clean announcement content with updated heading classifier")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    db_path = get_db_path()
    print(f"Database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, announce_no, title, raw_data FROM announcements WHERE raw_data IS NOT NULL AND raw_data != ''"
    ).fetchall()

    total = len(rows)
    updated = 0
    same = 0

    for row in rows:
        old_html = row["raw_data"]
        plain = strip_html_tags(old_html)
        if not plain:
            same += 1
            continue

        new_html = clean_announcement_content(plain)
        if new_html == old_html:
            same += 1
            continue

        updated += 1
        if args.dry_run:
            print(f"[DRY-RUN] id={row['id']} announce_no={row['announce_no']} would update")
            if updated <= 5:
                print(f"  OLD: {old_html[:200]}")
                print(f"  NEW: {new_html[:200]}")
                print()
        else:
            conn.execute(
                "UPDATE announcements SET raw_data = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (new_html, row["id"]),
            )
            print(f"[UPDATE] id={row['id']} announce_no={row['announce_no']}")

    if not args.dry_run:
        conn.commit()

    conn.close()

    print(f"\nTotal: {total}  Updated: {updated}  Unchanged: {same}")
    if args.dry_run:
        print("DRY-RUN mode: no changes written.")


if __name__ == "__main__":
    main()
