#!/usr/bin/env python3
"""存量公告正文清洗脚本。

筛选 content 长度 > 1000 字符的记录，调用 clean_announcement_content 清洗，
满足条件（长度缩减 > 50% 或 减少 > 500 字符）时更新。
事务控制 + 进度日志，可直接在容器内执行。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.announcement.matcher import clean_announcement_content
from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database


def main():
    db = Database(get_db_path())
    # 筛选待清洗记录
    rows = db.fetchall(
        "SELECT id, announce_no, raw_data FROM announcements WHERE raw_data IS NOT NULL AND LENGTH(raw_data) > 1000"
    )
    total = len(rows)
    print(f"待清洗: {total} 条")

    updated = 0
    skipped = 0
    for i, row in enumerate(rows):
        original = row["raw_data"]
        cleaned = clean_announcement_content(original)
        orig_len = len(original)
        clean_len = len(cleaned)

        reduction = orig_len - clean_len
        ratio = clean_len / orig_len if orig_len > 0 else 1

        # 仅当清洗效果显著时更新
        should_update = ratio < 0.5 or reduction > 500
        if should_update and cleaned:
            db.execute(
                "UPDATE announcements SET raw_data = ?, updated_at = datetime('now') WHERE id = ?",
                (cleaned, row["id"]),
            )
            updated += 1
        else:
            skipped += 1

        if (i + 1) % 100 == 0:
            print(f"  进度: {i + 1}/{total} | 已更新: {updated} | 跳过: {skipped}")

    print(f"\n完成: 总 {total} 条 | 更新 {updated} 条 | 跳过 {skipped} 条")
    db.close()


if __name__ == "__main__":
    main()
