#!/usr/bin/env python3
"""共享列表操作检查 — 检查 _parsed_results 等共享列表的操作安全性。

扫描 pilotstd/ui/core/handlers/ 下的 Python 文件：
1. 找出所有对 _parsed_results 的赋值（=）
2. 找出所有 clear/extend/append/pop/remove/del 操作
3. 找出所有 [:] = 切片赋值
4. 标记高风险操作（赋值非构造器传递 / [:] = 共享列表修改）

用法:
    python scripts/check_shared_list.py
    python scripts/check_shared_list.py --all  # 同时检查 _queried_items、_download_list 等

退出码: 0=全部安全, 1=发现高风险操作
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIR = ROOT / "pilotstd" / "ui"

# 要检查的共享列表变量名
SHARED_LISTS = [
    "_parsed_results",
    "_queried_items",
    "_query_results",
    "_download_list",
    "_expire_list",
    "_pending_list",
    "_download_tasks",
    "_unrecognized_files",
]


def check_file(file_path: Path, list_names: list[str]) -> list[tuple[int, str, str]]:
    """检查文件中的共享列表操作。
    返回 [(行号, 风险等级, 描述)]。
    """
    issues: list[tuple[int, str, str]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return issues

    for list_name in list_names:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # 模式1: self._parsed_results = some_list (赋值新引用)
            m = re.search(rf"self\.{list_name}\s*=\s*(\w+)", stripped)
            if m:
                rhs = m.group(1)
                # 构造器参数传递是安全的: self._xxx = xxx
                if rhs == list_name.lstrip("_"):  # self._parsed_results = parsed_results
                    continue  # 构造器传递，安全
                # 初始化为 [] 安全（但应在构造器中）
                if rhs == "[]":
                    continue  # 初始化，通常安全
                issues.append((i, "中", f"self.{list_name} = {rhs} → 赋值新引用，可能断裂共享"))

            # 模式2: self._parsed_results[:] = ... (切片赋值)
            if re.search(rf"self\.{list_name}\[:]\s*=", stripped):
                issues.append((i, "高", f"self.{list_name}[:] = ... → 切片赋值修改共享列表"))

            # 模式3: self._parsed_results.clear() (安全)
            if re.search(rf"self\.{list_name}\.clear\(\)", stripped):
                pass  # 原地清空，安全

            # 模式4: self._parsed_results.extend(...) (安全)
            if re.search(rf"self\.{list_name}\.extend\(.+\)", stripped):
                pass  # 原地扩展，安全

            # 模式5: self._parsed_results.append(...) (安全)
            if re.search(rf"self\.{list_name}\.append\(.+\)", stripped):
                pass  # 原地追加，安全

            # 模式6: del self._parsed_results[idx] (安全，原地删除)
            if re.search(rf"del\s+self\.{list_name}\[", stripped):
                pass  # 原地删除，安全

    return issues


def main() -> int:
    check_all = "--all" in sys.argv
    list_names = SHARED_LISTS if check_all else ["_parsed_results"]

    if not SCAN_DIR.exists():
        print(f"ERROR: 扫描目录不存在: {SCAN_DIR}")
        return 2

    py_files = sorted(p for p in SCAN_DIR.rglob("*.py") if "__pycache__" not in p.parts)

    all_issues: dict[Path, list[tuple[int, str, str]]] = {}
    for f in py_files:
        issues = check_file(f, list_names)
        if issues:
            all_issues[f] = issues

    # ── 输出 ──
    sep = "=" * 60
    print(sep)
    print("  共享列表操作安全检查")
    print(sep)
    print(f"  扫描目录: {SCAN_DIR.relative_to(ROOT)}")
    print(f"  扫描文件: {len(py_files)}")
    print(f"  检查变量: {', '.join(list_names)}")
    print(f"  有问题的文件: {len(all_issues)}")
    print()

    total_high = 0
    total_mid = 0

    for f, issues in sorted(all_issues.items()):
        rel = f.relative_to(ROOT)
        print(f"  --- {rel} ---")
        for lineno, level, desc in issues:
            marker = "[HIGH]" if level == "高" else "[MID] "
            print(f"    行 {lineno:4d} {marker} {desc}")
            if level == "高":
                total_high += 1
            else:
                total_mid += 1
        print()

    print(sep)
    print(f"  高风险: {total_high}, 中风险: {total_mid}")
    if total_high > 0:
        print(f"  FAIL: 发现 {total_high} 个高风险操作")
        return 1
    elif total_mid > 0:
        print(f"  WARN: 发现 {total_mid} 个中风险操作，请人工审查")
    else:
        print("  PASS: 所有共享列表操作安全")
    print(sep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
