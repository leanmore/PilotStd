"""tests/skip_census.py — 运行期跳过普查（T-20 / R11-4，2026-09-27）。

为什么需要它：T-20 原登记「`tests/` 运行期 `self.skipTest()` 共 **60 处 / 10 文件**」——R11-4 实测表明
这是**静态调用点**口径，与运行期真实跳过数不是一回事（本地 14、CI 44）。本工具把两者分开统计：

  · 运行期口径：解析 `pytest -rs` 的 `SKIPPED [n] path:line: reason` 行，按原因分类汇总；
  · 静态口径：AST 统计 `self.skipTest()`、`pytest.skip()`、`@pytest.mark.skip`、
    `@pytest.mark.skipif`、`@unittest.skipIf/skipUnless` 五类标记的调用点数。

用法：
  python -m pytest tests/ -q -rs --ignore=tests/gui/ > skip.txt 2>&1
  python tests/skip_census.py skip.txt            # 运行期分类报告
  python tests/skip_census.py skip.txt --json     # 机器可读
  python tests/skip_census.py --static            # 只出静态口径清单

分类规则（顺序即优先级，命中即返回）：
  fixture（缺 fixture）→ random（随机兜底）→ platform（平台/文件系统能力）→
  network（站点/网络）→ dependency（需要真实组件/线程/外部 provider）→ other。
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fixture", ("fixture",)),
    ("random", ("概率极低", "随机", "连续20次")),
    ("platform", ("系统不支持", "平台", "文件名")),
    ("network", ("无响应", "未收录", "无结果", "网络", "http", "请求", "轮转器", "外部 api", "站点")),
    ("dependency", ("依赖", "需要", "daemon", "threadpoolexecutor", "provider", "未安装")),
)
DEFAULT_CATEGORY = "other"

# `SKIPPED [1] tests/x.py:42: 原因` —— 原因可能为空
_SKIP_LINE = re.compile(r"^SKIPPED\s+\[(\d+)\]\s+(?P<loc>.+?):(?P<line>\d+):\s*(?P<reason>.*)$")


@dataclass(frozen=True)
class SkipRecord:
    """一条运行期跳过记录。"""

    test_file: str
    line: int
    reason: str
    category: str


def classify(reason: str) -> str:
    """按 CATEGORY_RULES 给跳过原因分类。"""
    text = (reason or "").lower()
    for category, keywords in CATEGORY_RULES:
        if any(k in text for k in keywords):
            return category
    return DEFAULT_CATEGORY


def parse_rs_report(text: str) -> list[SkipRecord]:
    """解析 `pytest -rs` 短摘要，返回跳过记录（含 `[n]` 倍数展开）。"""
    records: list[SkipRecord] = []
    for raw in (text or "").splitlines():
        match = _SKIP_LINE.match(raw.strip())
        if not match:
            continue
        count = int(match.group(1))
        reason = match.group("reason").strip()
        for _ in range(max(count, 1)):
            records.append(
                SkipRecord(
                    test_file=match.group("loc").strip().replace("\\", "/"),
                    line=int(match.group("line")),
                    reason=reason,
                    category=classify(reason),
                )
            )
    return records


def summarize(records: list[SkipRecord]) -> dict:
    """按分类与文件汇总。"""
    return {
        "total": len(records),
        "by_category": dict(Counter(r.category for r in records).most_common()),
        "by_file": dict(Counter(r.test_file for r in records).most_common()),
    }


# ── 静态口径：五类跳过标记的调用点计数 ────────────────────────────────────────


def _decorator_names(node: ast.AST) -> list[str]:
    """取函数/类上所有装饰器的点分名（如 pytest.mark.skip、unittest.skipIf）。"""
    names: list[str] = []
    for dec in getattr(node, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        parts: list[str] = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        if parts:
            names.append(".".join(reversed(parts)))
    return names


def static_inventory() -> dict:
    """AST 统计 tests/ 下五类跳过标记的调用点数（不执行任何测试）。

    `pytest_skip` 只统计**函数体内**的 `pytest.skip()` 调用；装饰器位置的
    `@pytest.mark.skip(reason=...)` 归入 `mark_skip`，不重复计数。
    """
    buckets: dict[str, list[str]] = {
        "skipTest": [],
        "pytest_skip": [],
        "mark_skip": [],
        "mark_skipif": [],
        "unittest_cond": [],
    }
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        decorator_calls = {
            id(dec)
            for node in ast.walk(tree)
            if hasattr(node, "decorator_list")
            for dec in node.decorator_list
            if isinstance(dec, ast.Call)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "skipTest":
                    buckets["skipTest"].append(f"{rel}:{node.lineno}")
                elif isinstance(func, ast.Attribute) and func.attr == "skip" and id(node) not in decorator_calls:
                    buckets["pytest_skip"].append(f"{rel}:{node.lineno}")
            for name in _decorator_names(node):
                if name == "pytest.mark.skip":
                    buckets["mark_skip"].append(f"{rel}:{node.lineno}")
                elif name == "pytest.mark.skipif":
                    buckets["mark_skipif"].append(f"{rel}:{node.lineno}")
                elif name in ("unittest.skipIf", "unittest.skipUnless"):
                    buckets["unittest_cond"].append(f"{rel}:{node.lineno}")
    return {
        "counts": {key: len(value) for key, value in buckets.items()},
        "sites": buckets,
    }


def main(argv: list[str]) -> int:
    """CLI 入口：报告文件路径或 `--static`。"""
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    if "--static" in argv:
        payload = {"mode": "static", **static_inventory()}
    else:
        if not args:
            print(__doc__)
            return 2
        text = Path(args[0]).read_text(encoding="utf-8", errors="replace")
        records = parse_rs_report(text)
        payload = {
            "mode": "runtime",
            "report": args[0],
            "summary": summarize(records),
            "records": [f"{r.test_file}:{r.line} [{r.category}] {r.reason}" for r in records],
        }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"[skip-census] 模式={payload['mode']}")
        if payload["mode"] == "runtime":
            summary = payload["summary"]
            print(f"  运行期跳过总数: {summary['total']}")
            for category, count in summary["by_category"].items():
                print(f"    {category:12s} {count}")
            for test_file, count in summary["by_file"].items():
                print(f"    {test_file}  ×{count}")
        else:
            for key, count in payload["counts"].items():
                print(f"    {key:16s} {count}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    sys.exit(main(sys.argv[1:]))
