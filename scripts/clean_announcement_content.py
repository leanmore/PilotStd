#!/usr/bin/env python3
"""存量公告正文清洗脚本（v2 — 语义 class 判定替代长度/缩减率阈值）。

用法:
    python scripts/clean_announcement_content.py              # 实际写入
    python scripts/clean_announcement_content.py --dry-run    # 仅预览，不写库
    python scripts/clean_announcement_content.py --verbose    # 逐条打印清洗前后对比

判定逻辑: 只要 raw_data 不含 'class="announce-body"' 就触发清洗。
预处理: 现有 raw_data 可能含原始 <p> 标签，清洗前先提取纯文本再送入管线。
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.announcement._content_cleaner import clean_announcement_content
from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database


def needs_cleaning(raw_html: str) -> bool:
    """只要缺少语义 class 就判定需要清洗。"""
    if not raw_html or not raw_html.strip():
        return False
    return 'class="announce-body"' not in raw_html


def preprocess(html: str) -> str:
    """将可能含 <p> 标签的 HTML 转为纯文本，供 clean_announcement_content 处理。

    clean_announcement_content 的输入契约是纯文本（无 HTML 标签），
    但生产数据中 raw_data 可能保留了原始 <p> 标签。
    """
    if not html or not html.strip():
        return ""
    # 如果已经是纯文本（无网页标签），直接返回
    if "<" not in html:
        return html
    # 提取所有标签内的文本，保持段落分隔
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
    if paragraphs:
        return "\n\n".join(p.strip() for p in paragraphs if p.strip())
    # 回退：去除所有网页标签
    clean = re.sub(r"<[^>]+>", "", html)
    return clean.strip()


def main():
    parser = argparse.ArgumentParser(description="存量公告正文清洗")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入数据库")
    parser.add_argument("--verbose", "-v", action="store_true", help="逐条打印清洗前后对比")
    args = parser.parse_args()

    db = Database(get_db_path())

    # 筛选：有内容且未清洗过的记录（去掉长度限制）
    rows = db.fetchall(
        "SELECT id, announce_no, source_site, raw_data, title"
        " FROM announcements"
        " WHERE raw_data IS NOT NULL AND raw_data != ''"
        " ORDER BY id"
    )
    total = len(rows)
    print(f"待检查: {total} 条")

    to_clean = []
    for row in rows:
        if needs_cleaning(row["raw_data"]):
            to_clean.append(row)

    print(f"需清洗: {len(to_clean)} 条（缺少语义 class）")
    print(f"跳过:   {total - len(to_clean)} 条（已有语义 class 或内容为空）")
    print()

    if not to_clean:
        print("无需清洗。")
        db.close()
        return

    updated = 0
    for i, row in enumerate(to_clean):
        original = row["raw_data"]
        plain_text = preprocess(original)
        cleaned = clean_announcement_content(plain_text)

        if args.verbose:
            print(f"--- [{i + 1}/{len(to_clean)}] {row['announce_no'][:40]} ---")
            print(f"  原始 ({len(original)} chars): {original[:150]}...")
            print(f"  清洗 ({len(cleaned)} chars): {cleaned[:150]}...")
            print()

        if args.dry_run:
            if (i + 1) % 20 == 0:
                print(f"  dry-run 进度: {i + 1}/{len(to_clean)}")
            continue

        if cleaned:
            db.execute(
                "UPDATE announcements SET raw_data = ?, updated_at = datetime('now') WHERE id = ?",
                (cleaned, row["id"]),
            )
            updated += 1

        if (i + 1) % 20 == 0:
            print(f"  写入进度: {i + 1}/{len(to_clean)} | 已更新: {updated}")

    if args.dry_run:
        print(f"\ndry-run 完成: 将清洗 {len(to_clean)}/{total} 条")
        # 展示首尾各 2 条清洗效果
        print("\n=== 清洗效果预览（首 2 条）===")
        for row in to_clean[:2]:
            plain = preprocess(row["raw_data"])
            cleaned = clean_announcement_content(plain)
            print(f"  [{row['announce_no'][:35]}]")
            print(f"    原始: {row['raw_data'][:120]}")
            print(f"    清洗: {cleaned[:120]}")
            print()
        print("=== 清洗效果预览（末 2 条）===")
        for row in to_clean[-2:]:
            plain = preprocess(row["raw_data"])
            cleaned = clean_announcement_content(plain)
            print(f"  [{row['announce_no'][:35]}]")
            print(f"    原始: {row['raw_data'][:120]}")
            print(f"    清洗: {cleaned[:120]}")
            print()
    else:
        print(f"\n完成: 更新 {updated}/{len(to_clean)} 条")

    db.close()


if __name__ == "__main__":
    main()
