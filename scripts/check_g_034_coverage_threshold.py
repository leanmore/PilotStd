#!/usr/bin/env python3
"""G-034: 覆盖率阈值检查。

从 `docs/testing/coverage-report.md` 读取整体行覆盖率，与**唯一来源**的阈值比较。
阻断条件：文件不存在、解析不出数据、或覆盖率低于阈值。

2026-10-17 两项修正（体检 A-3 / B-1）：
1. **解析器**：原正则只认 `行覆盖率: 85.2%` 这种冒号写法，而生成器实际产出的是**表格行**
   `| 行覆盖率 | **62.5%** |` ⇒ 永不匹配 ⇒ 门禁恒报"无法解析"（且它当时还未接线，故无人察觉）。
   现补表格行候选，并保留原有各种写法作为兼容。
2. **阈值单一来源**：原在本脚本硬编码 80.0，而项目里同时存在 `pyproject.toml` 的 `fail_under`
   与 CI 各作业的 `--cov-fail-under` ⇒ **四套口径**（51 / 45 / 58 / 80），任何按 `gates.md`
   判断"达标线"的人都会得出错误结论。现改为读 `pyproject.toml` 的 `[tool.coverage.report] fail_under`
   作为权威值；读不到才退回 `FALLBACK_THRESHOLD`。**80% 降级为长期目标**（棘轮式提升，见 gates.md）。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_REPORT = ROOT / "docs" / "testing" / "coverage-report.md"

# 阈值解析与覆盖率生成器共用同一实现（2026-10-17 体检 B-1：四套口径收敛为单一来源）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coverage_threshold import (  # noqa: E402
    FALLBACK_THRESHOLD,
    resolve_threshold,
)

__all__ = ["FALLBACK_THRESHOLD", "parse_coverage", "resolve_threshold"]


def parse_coverage(text: str) -> float | None:
    """从覆盖率报告文本中提取整体行覆盖率百分比。

    候选顺序：**表格行**（生成器的真实输出）→ 冒号写法 → 英文 → 兜底 `TOTAL`。
    """
    patterns = [
        # 生成器真实输出：| 行覆盖率 | **62.5%** |
        r"行覆盖率\s*\|\s*\**\s*([\d.]+)\s*%",
        r"行覆盖率[：:]\s*([\d.]+)\s*%",
        r"Line\s*Coverage\s*\|\s*\**\s*([\d.]+)\s*%",
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
    """入口：从覆盖率报告解析行覆盖率百分比，与阈值对比。"""
    print("G-034: 覆盖率阈值检查")
    print("=" * 60)

    if not COVERAGE_REPORT.exists():
        print(f"FAIL: {COVERAGE_REPORT} 不存在，请先运行覆盖率 job 生成报告。")
        return 1

    threshold = resolve_threshold()
    text = COVERAGE_REPORT.read_text(encoding="utf-8")
    coverage = parse_coverage(text)

    if coverage is None:
        print(f"FAIL: 无法从 {COVERAGE_REPORT} 中解析覆盖率数据。")
        print("请确保报告中包含形如 '| 行覆盖率 | **85.2%** |' 的表格行（或 '行覆盖率: 85.2%' 的行）。")
        return 1

    print(f"覆盖率: {coverage:.1f}%")
    print(f"阈值: {threshold:.0f}%（来源：pyproject.toml 的 fail_under）")

    if coverage < threshold:
        print(f"\nFAIL: 覆盖率 {coverage:.1f}% 低于阈值 {threshold:.0f}%。")
        return 1

    print(f"\nPASS: 覆盖率 {coverage:.1f}% ≥ {threshold:.0f}% 阈值。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
