#!/usr/bin/env python3
"""G-034: 覆盖率阈值检查。

从 docs/testing/coverage-report.md 读取整体行覆盖率，
检查是否 ≥ 80% 阈值。
阻断条件：文件不存在，或覆盖率 < 80%。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_REPORT = ROOT / "docs" / "testing" / "coverage-report.md"
THRESHOLD = 80.0


def parse_coverage(text: str) -> float | None:
    """从覆盖率报告文本中提取整体行覆盖率百分比。"""
    patterns = [
        r"行覆盖率[：:]\s*([\d.]+)\s*%",
        r"Line\s*Coverage[：:]\s*([\d.]+)\s*%",
        r"整体.*覆盖率[：:]\s*([\d.]+)\s*%",
        r"覆盖率[：:]\s*([\d.]+)\s*%",
        r"coverage[：:]\s*([\d.]+)\s*%",
        r"TOTAL.*?\b([\d.]+)\s*%",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


def main() -> int:
    print("G-034: 覆盖率阈值检查")
    print("=" * 60)

    if not COVERAGE_REPORT.exists():
        print(f"FAIL: {COVERAGE_REPORT} 不存在，请先运行覆盖率 job 生成报告。")
        return 1

    text = COVERAGE_REPORT.read_text(encoding="utf-8")
    coverage = parse_coverage(text)

    if coverage is None:
        print(f"FAIL: 无法从 {COVERAGE_REPORT} 中解析覆盖率数据。")
        print("请确保报告中包含形如 '行覆盖率: 85.2%' 的行。")
        return 1

    print(f"覆盖率: {coverage:.1f}%")
    print(f"阈值: {THRESHOLD:.0f}%")

    if coverage < THRESHOLD:
        print(f"\nFAIL: 覆盖率 {coverage:.1f}% 低于阈值 {THRESHOLD:.0f}%。")
        return 1

    print(f"\nPASS: 覆盖率 {coverage:.1f}% ≥ {THRESHOLD:.0f}% 阈值。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
