#!/usr/bin/env python3
"""自动更新文档中的可量化数据（测试数、文件引用、聚合器描述等）。"""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
STATUS_FILE = PROJECT_ROOT / "STATUS.md"
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"


def extract_test_count() -> int:
    """从 STATUS.md 提取测试数。"""
    if not STATUS_FILE.exists():
        return 0
    content = STATUS_FILE.read_text(encoding="utf-8")
    m = re.search(r"Python\s+(\d+)\s+tests? collected", content)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s+passed", content)
    return int(m.group(1)) if m else 0


def update_test_count(filepath: Path, count: int) -> bool:
    """更新文件中的测试数引用。"""
    if not filepath.exists() or count == 0:
        return False
    content = filepath.read_text(encoding="utf-8")
    original = content

    # 替换模式：数字 + PASS / 数字 + passed
    for pat in (r"\d+\s+PASS", r"\d+\s+passed", r"\d+\s+tests? passed"):
        content = re.sub(pat, f"{count} PASS", content)

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def update_aggregator_desc() -> bool:
    """从 aggregate_buffer.py 读取当前配置，更新 STATUS.md 描述。"""
    agg_file = PROJECT_ROOT / "pilotstd/core/notification/aggregate_buffer.py"
    if not agg_file.exists() or not STATUS_FILE.exists():
        return False

    agg_src = agg_file.read_text(encoding="utf-8")
    window_m = re.search(r"DEFAULT_WINDOW_SECONDS\s*=\s*([\d.]+)", agg_src)
    max_m = re.search(r"MAX_WINDOW_SECONDS\s*=\s*([\d.]+)", agg_src)
    batch_m = re.search(r"DEFAULT_BATCH_SIZE\s*=\s*(\d+)", agg_src)

    if not window_m or not max_m:
        return False

    window_s = float(window_m.group(1))
    max_s = float(max_m.group(1))
    batch = batch_m.group(1) if batch_m else "20"
    strategy = "固定窗口" if "固定窗口" in agg_src else "滑动窗口"

    new_desc = f"聚合器架构 | {strategy} + 首次延时（{int(window_s)}s/{int(max_s)}s）+ 批次上限 {batch} 条"

    content = STATUS_FILE.read_text(encoding="utf-8")
    original = content
    content = re.sub(
        r"\|\s*聚合器[^\|]*\|[^\|]*\|",
        f"| {new_desc} |",
        content,
    )
    if content != original:
        STATUS_FILE.write_text(content, encoding="utf-8")
        return True
    return False


def update_tech_debt() -> bool:
    """更新 technical-debt-registry.md 中已过时的条目。"""
    fp = DOCS_DIR / "architecture/technical-debt-registry.md"
    if not fp.exists():
        return False

    content = fp.read_text(encoding="utf-8")
    original = content

    # 条目 #9: Toast 已删除
    if "Toast" in content and "已移除" not in content:
        content = re.sub(
            r"(\| 9 \| Toast[^|]*\|)[^|]*\|[^|]*\|[^|]*\|",
            r"\1 2026-07-09 | 已关闭 | Toast 组件及配置已全部移除 |",
            content,
        )
    # 条目 #16: stderr 修复已回退
    if "stderr" in content and "已回退" not in content:
        content = re.sub(
            r"(\| 16 \| PyInstaller[^|]*\|)[^|]*\|[^|]*\|[^|]*\|",
            r"\1 2026-07-09 | 已回退 | _SafeStream 已禁用 |",
            content,
        )
    # 更新测试数
    count = extract_test_count()
    if count:
        content = re.sub(
            r"\|\s*11\s*\|.*?\d+\s+PASS",
            f"| 11 | 测试覆盖 | 低 | 2026-06-29 | 已接受 | {count} PASS",
            content,
        )

    if content != original:
        fp.write_text(content, encoding="utf-8")
        return True
    return False


def git_add(*paths: Path) -> None:
    """git add 指定的文件。"""
    for p in paths:
        if p.exists():
            subprocess.run(["git", "add", str(p)], check=False)


def main() -> int:
    changed: list[Path] = []
    count = extract_test_count()

    # 同步测试数
    for doc in [DOCS_DIR / "development.md", DOCS_DIR / "index.md"]:
        if update_test_count(doc, count):
            changed.append(doc)

    # 聚合器描述
    if update_aggregator_desc():
        changed.append(STATUS_FILE)

    # 技术债务
    if update_tech_debt():
        changed.append(DOCS_DIR / "architecture/technical-debt-registry.md")

    if changed:
        git_add(*changed)
        names = ", ".join(p.name for p in changed)
        print(f"  文档自动更新: {names}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
