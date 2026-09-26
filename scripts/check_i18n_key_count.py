#!/usr/bin/env python3
"""i18n key 数量监控与键名对齐检查 — 轻量级，适合 CI 集成。

版本历史:
  v1.0.0  2026-07-29  初始版本：顶层 key 对齐检查 + 数量阈值监控 (50warn/60fail)
  v1.0.1  2026-07-29  修复 extra 检测逻辑：改用“其他文件并集”替代“全集”比较
  v1.1.0  2026-09-26  新增**叶子键路径**对齐检查（v1.0.x 只比顶层，看不见
                      `nav.archive` / `home.tasks` 这类叶子漂移——实测三语 142/143/143
                      时本脚本仍报 PASS）。叶子路径不一致 → 阻断；空对象 `{}` 记为一个叶子
                      （空壳 key 也算“存在”，否则漏报）。

触发阈值（技术债 #3）：
  - key 数 >= 50: workflow warning annotation
  - key 数 >= 60: 阻断（error），强制启动自动化检查方案

同时检测各 locale 文件顶层 key 是否对齐，以及**叶子键路径**是否三语一致，发现缺失立即报错。

关联测试: tests/test_i18n_key_count.py (14 用例)
关联文档: docs/technical-debt.md #3, docs/reference/i18n-troubleshooting-sop.md
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


def leaf_paths(data: dict[str, object], prefix: str = "") -> set[str]:
    """返回叶子键路径集合（如 settings.tasks.scan）。

    对象继续下钻；**空对象 `{}` 记为一个叶子**——它代表一个真实存在的 key，
    若某个语种没有它，就是漂移，不能被静默放过。
    """
    paths: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict) and value:
            paths |= leaf_paths(value, path)
        else:
            paths.add(path)
    return paths


def main() -> int:
    locales = load_locale_files()
    if not locales:
        print("::warning::No locale files found")
        return 0

    # 收集各文件的顶层集合
    file_keys: dict[str, set[str]] = {}
    for name, data in locales.items():
        file_keys[name] = top_level_keys(data)

    # 计算全集
    all_keys: set[str] = set()
    for keys in file_keys.values():
        all_keys.update(keys)

    # ──对齐检查：每个文件的顶层必须与全集一致──
    aligned = True
    for name, keys in sorted(file_keys.items()):
        # 本文件缺失的（其他文件有，本文件没有）
        missing = all_keys - keys
        # 本文件独有的（本文件有，其他所有文件都没有）
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

    # ── v1.1.0 叶子键路径对齐（顶层一致 ≠ 三语一致；漂移往往只发生在叶子层）──
    file_leaves: dict[str, set[str]] = {name: leaf_paths(data) for name, data in locales.items()}
    all_leaves: set[str] = set()
    for leaves in file_leaves.values():
        all_leaves |= leaves
    leaf_aligned = True
    for name, leaves in sorted(file_leaves.items()):
        leaf_missing = all_leaves - leaves
        if leaf_missing:
            preview = sorted(leaf_missing)
            shown = preview[:5]
            suffix = f" …共 {len(preview)} 个" if len(preview) > 5 else ""
            print(f"::error file={name}::叶子 key 缺失（其他语种有、本文件没有）: {shown}{suffix}")
            leaf_aligned = False

    # 输出摘要表
    print("| 文件 | 顶层 key 数 | 叶子 key 数 |")
    print("|------|------------|------------|")
    for name in sorted(file_keys):
        count = len(file_keys[name])
        print(f"| {name} | {count} | {len(file_leaves[name])} |")
    leaf_counts = {len(leaves) for leaves in file_leaves.values()}
    print(f"\n全集 key 数: {len(all_keys)}，最大单文件: {max_file} ({max_keys} key)")
    print(
        f"叶子 key 数: {dict(sorted((n, len(v)) for n, v in file_leaves.items()))}"
        f"，全集 {len(all_leaves)}，三语一致: {len(leaf_counts) == 1 and leaf_aligned}"
    )

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

    if not leaf_aligned:
        print("::error::Locale 文件叶子 key 路径不一致（三语必须逐键对齐），请在合并前修复。")
        return 1

    print("i18n key count check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
