#!/usr/bin/env python3
"""i18n key 数量监控与键名对齐检查 — 轻量级，适合 CI 集成。

触发阈值（技术债 #3）：
  - key 数 >= 50: workflow warning annotation
  - key 数 >= 60: 阻断（error），强制启动自动化检查方案

同时检测各 locale 文件顶层 key 是否对齐，发现缺失立即报错。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LOCALE_DIR = Path("web/src/locales")
WARN_THRESHOLD = 50  # 发出警告
FAIL_THRESHOLD = 60  # 阻断，强制启动自动化检查


def load_locale_files() -> dict[str, dict[str, object]]:
    """加载所有 locale JSON 文件，返回 {文件名: 解析后的 dict}。"""
    if not LOCALE_DIR.is_dir():
        print(f"::error::Locale directory not found: {LOCALE_DIR}")
        sys.exit(1)

    locales: dict[str, dict[str, object]] = {}
    for f in sorted(LOCALE_DIR.glob("*.json")):
        try:
            locales[f.name] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"::error::{f.name} JSON 解析失败: {e}")
            sys.exit(1)
    return locales


def top_level_keys(data: dict[str, object]) -> set[str]:
    """返回顶层 key 集合。"""
    return set(data.keys())


def main() -> int:
    locales = load_locale_files()
    if not locales:
        print("::warning::No locale files found")
        return 0

    # 收集各文件的顶层 key 集合
    file_keys: dict[str, set[str]] = {}
    for name, data in locales.items():
        file_keys[name] = top_level_keys(data)

    # 计算全集
    all_keys: set[str] = set()
    for keys in file_keys.values():
        all_keys.update(keys)

    # ── 对齐检查：每个文件的顶层 key 必须与全集一致 ──
    aligned = True
    for name, keys in sorted(file_keys.items()):
        # 本文件缺失的 key（其他文件有，本文件没有）
        missing = all_keys - keys
        # 本文件独有的 key（本文件有，其他所有文件都没有）
        others = set().union(*(v for k, v in file_keys.items() if k != name))
        extra = keys - others
        if missing:
            print(f"::error file={name}::顶层 key 缺失（相对于其他 locale 文件）: {sorted(missing)}")
            aligned = False
        if extra:
            print(f"::warning file={name}::顶层 key 仅本文件存在（其他 locale 文件缺失）: {sorted(extra)}")

    # ── 数量监控 ──
    max_keys = max(len(keys) for keys in file_keys.values())
    max_file = max(file_keys, key=lambda n: len(file_keys[n]))

    # 输出摘要表
    print("| 文件 | 顶层 key 数 |")
    print("|------|------------|")
    for name in sorted(file_keys):
        count = len(file_keys[name])
        print(f"| {name} | {count} |")
    print(f"\n全集 key 数: {len(all_keys)}，最大单文件: {max_file} ({max_keys} key)")

    if max_keys >= FAIL_THRESHOLD:
        print(
            f"::error title=i18n Key Count::{max_file} 已达 {max_keys} 个顶层 key，"
            f"超过阻断阈值 {FAIL_THRESHOLD}。请立即实施 i18n key 一致性自动化检查"
            f"（见 docs/technical-debt.md #3）。"
        )
        return 1

    if max_keys >= WARN_THRESHOLD:
        print(
            f"::warning title=i18n Key Count Approaching Threshold::"
            f"{max_file} 已有 {max_keys} 个顶层 key，接近阻断阈值 {FAIL_THRESHOLD}。"
            f"建议开始评估自动化检查方案（见 docs/technical-debt.md #3）。"
        )

    if not aligned:
        print("::error::Locale 文件顶层 key 不一致，请在合并前修复。")
        return 1

    print("i18n key count check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
