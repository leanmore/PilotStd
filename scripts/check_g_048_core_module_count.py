#!/usr/bin/env python3
"""
G-048: 架构文档模块计数一致性
断言 docs/architecture/modules/core.md 中「子模块数」声明的数字，等于
pilotstd/core/ 下递归全部 .py 文件数（含 __init__.py，不含 __pycache__）。

起因：该行自 2026-10-01 起连续漂移 12 个文件（74 → 86）而长期无人察觉——因为它不在
任何门禁的比对范围内（G-031 只校验"文档存在且映射齐全"，不校验文档里的内容数字）。
本门禁把"漂移"从"事后考古"变成"提交即红"。
"""

import re
import sys
from pathlib import Path

# 控制台-8编码兼容（与同目录其它门禁脚本同口径）
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC = PROJECT_ROOT / "docs" / "architecture" / "modules" / "core.md"
PKG = PROJECT_ROOT / "pilotstd" / "core"

# 只认「子模块数」行里紧跟其后的首个数字，避免误取同行其它数字（如历史括注里的编号）
ROW_RE = re.compile(r"^\|\s*子模块数\s*\|\s*(\d+)\s*个", re.MULTILINE)


def declared_count() -> int | None:
    """读取架构文档声明的子模块数；行不存在或格式变化时返回 None。"""
    match = ROW_RE.search(DOC.read_text(encoding="utf-8"))
    return int(match.group(1)) if match else None


def actual_count() -> int:
    """递归统计包内 .py 文件数：含 __init__.py，排除 __pycache__ 下的缓存。"""
    return sum(1 for path in PKG.rglob("*.py") if "__pycache__" not in path.parts)


def main() -> int:
    """比对声明值与实际值，不一致即阻断并给出同步指引。"""
    declared = declared_count()
    actual = actual_count()

    if declared is None:
        print("❌ G-048 失败：未能从架构文档解析「子模块数」行")
        print(f"  文档: {DOC.relative_to(PROJECT_ROOT)}")
        print("  期望格式: | 子模块数 | <数字> 个 ... |")
        return 1

    if declared != actual:
        print("❌ G-048 失败：架构文档的模块计数与实际不符")
        print(f"  文档声明: {declared}")
        print(f"  实际统计: {actual}（递归 *.py，含 __init__.py，不含 __pycache__）")
        print(f"  处理: 在 {DOC.relative_to(PROJECT_ROOT)} 的「子模块数」行同步该数字（同一 commit）")
        return 1

    print(f"✅ G-048 通过：架构文档子模块数 = 实际 .py 文件数 = {actual}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
