#!/usr/bin/env python3
"""迁移误归档到「 未知行业()」目录的文件到正确行业目录。

背景：前端归档步骤曾漏传 logical_code，导致 PDF 文件全部归档到
/standards/ 未知行业()/ 目录（目录名带前导空格，空括号被误读为"未知行业0"）。

恢复原理：误归档文件名格式为 " {num_prefix}{number}-{year} {name}.pdf"，
其中 num_prefix 是前端误传的 logical_code（bug 副产物）。file_index 表的
number/year 是权威值，用它从文件名前缀末尾剥离 number，剩余部分即正确的
logical_code。

用法:
    python scripts/migrate_unknown_industry.py              # 实际迁移
    python scripts/migrate_unknown_industry.py --dry-run    # 仅预览，不动文件
    python scripts/migrate_unknown_industry.py --verbose    # 逐条打印明细
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database
from pilotstd.organizer.industry_lookup import get_folder_name


def recover_logical_code(filename: str, number: int, year: int) -> str:
    """从污染文件名恢复逻辑代号。

    误归档文件名格式: " {num_prefix}{number}-{year} {name}.pdf"，
    num_prefix 为前端误传的 logical_code。用 number 从前缀末尾剥离。
    """
    # 文件名以 "-年份" 分隔，前缀 = num_prefix + number
    name = filename.strip()
    idx = name.find(f"-{year}")
    if idx == -1:
        return ""
    prefix = name[:idx]
    num_str = str(number)
    if prefix.endswith(num_str):
        return prefix[: -len(num_str)].strip()
    return prefix.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移误归档到「未知行业()」目录的文件")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不移动文件、不写库")
    parser.add_argument("--verbose", "-v", action="store_true", help="逐条打印迁移明细")
    args = parser.parse_args()

    # 从索引表查所有误归档记录（目录名含"未知行业()"）
    db = Database(get_db_path())
    rows = db.fetchall(
        "SELECT id, file_path, number, year FROM file_index"
        " WHERE file_path LIKE ? ORDER BY file_path",
        ("%未知行业()%",),
    )
    if not rows:
        print("未发现误归档记录")
        return

    # 从第一条记录推断库根目录（/standards）
    root = os.path.dirname(os.path.dirname(rows[0]["file_path"]))
    print(f"库根目录: {root}")
    print(f"待迁移: {len(rows)} 条")

    moved = 0
    skipped = 0
    failed = 0
    for row in rows:
        old_path = row["file_path"]
        number = row["number"]
        year = row["year"]
        filename = os.path.basename(old_path)

        if not os.path.isfile(old_path):
            skipped += 1
            if args.verbose:
                print(f"[跳过] 文件不存在: {old_path}")
            continue

        logical_code = recover_logical_code(filename, number, year)
        if not logical_code:
            failed += 1
            print(f"[失败] 无法恢复逻辑代号: {old_path} (number={number}, year={year})")
            continue

        # 用恢复的代号生成正确行业目录
        folder = get_folder_name(logical_code)
        new_dir = os.path.join(root, folder)
        new_path = os.path.join(new_dir, filename.strip())

        if args.dry_run:
            moved += 1
            print(f"[预览] {old_path} -> {new_path}")
            continue

        try:
            # 先建目录再移动，移动成功后同步修正索引
            os.makedirs(new_dir, exist_ok=True)
            shutil.move(old_path, new_path)
            db.execute(
                "UPDATE file_index SET file_path=?, logical_code=? WHERE id=?",
                (new_path, logical_code, row["id"]),
            )
            moved += 1
            if args.verbose:
                print(f"[迁移] {old_path} -> {new_path}")
        except OSError as exc:
            failed += 1
            print(f"[失败] {old_path}: {exc}")

    # 删除空的误归档目录
    if not args.dry_run:
        for dirpath, dirnames, _files in os.walk(root, topdown=False):
            for d in dirnames:
                if "未知行业" in d:
                    target = os.path.join(dirpath, d)
                    try:
                        if not os.listdir(target):
                            os.rmdir(target)
                            print(f"[清理] 删除空目录: {target}")
                    except OSError as exc:
                        print(f"[警告] 目录未删除(可能非空): {target} ({exc})")

    print(f"完成: 迁移 {moved}, 跳过 {skipped}, 失败 {failed}")


if __name__ == "__main__":
    main()
