#!/usr/bin/env python3
"""G-050：静默吞错棘轮门禁（体检 D-8 / D-9 / D-10 的存量锁）。

扫描 `pilotstd/` 与 `docker/`，统计三类"失败不可见"：
1. `except` 体只有 `pass`（D-8）；
2. `except` 体只有 `return <空/False/None>`（D-9 的严格口径）；
3. `except` 体内调用 `logger.debug`（D-10）。

与 `scripts/silent_errors_baseline.json`（按文件 × 类别计数）比较：
- 当前 > 基线 → FAIL（新增了不可见的失败路径）；
- 当前 < 基线 → WARN（存量已减少，可收紧基线）。

刻意排除 `pilotstd/templates/`（Jinja 脚手架，非运行时代码）。迁移文件计入基线：
受 P-106 约束不能改源码，基线只用于阻止新增。

用法：
    python scripts/check_g_050_silent_errors.py            # 门禁判定
    python scripts/check_g_050_silent_errors.py --emit     # 打印当前基线 JSON
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "silent_errors_baseline.json"
# 扫描范围：与 G-010 / G-038 同口径的生产代码目录
SCAN_DIRS = ("pilotstd", "docker")
# templates 是 Jinja2 脚手架（含 {{ }}），不是运行时代码，整体排除
EXCLUDE_PARTS = {"templates", "__pycache__"}
EMPTY_RETURN = (None, True, False, "", 0)


def _is_empty_return(value: ast.expr | None) -> bool:
    """`return` 的值是否属"空/假"。

    必须按类型判定 `0`：Python 里 `1 == True`，若用 `in (None, True, False, 0)`
    会把 `return 1` 误判成"假成功"（本门禁初版实测踩过）。
    """
    if value is None:
        return True
    if isinstance(value, ast.Constant):
        const = value.value
        if const is None or const is True or const is False or const == "":
            return True
        return type(const) is int and const == 0
    if isinstance(value, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
        return not (getattr(value, "keys", None) or getattr(value, "elts", None))
    return False


def _handler_kinds(node: ast.ExceptHandler) -> set[str]:
    """返回该 handler 命中的类别（pass / return / debug）。"""
    kinds: set[str] = set()
    # 只认"handler 体只有一条语句"的情况：多语句说明做了补救动作，不算静默吞错
    if len(node.body) == 1:
        stmt = node.body[0]
        if isinstance(stmt, ast.Pass):
            kinds.add("pass")
        elif isinstance(stmt, ast.Return) and _is_empty_return(stmt.value):
            kinds.add("return")
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "debug"
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == "logger"
        ):
            kinds.add("debug")
    return kinds


def scan(root: Path) -> dict[str, dict[str, int]]:
    """统计 root 下三类静默吞错的 (类别 → 文件 → 次数)。

    迁移文件也计入：它们受 P-106 约束不能改源码，但同样不允许新增吞错。
    `templates/` 是 Jinja 脚手架（非运行时代码），整体排除。
    """
    counts: dict[str, dict[str, int]] = {"pass": {}, "return": {}, "debug": {}}
    for dirname in SCAN_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if EXCLUDE_PARTS & set(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            rel = path.relative_to(root).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    for kind in _handler_kinds(node):
                        bucket = counts[kind]
                        bucket[rel] = bucket.get(rel, 0) + 1
    return counts


def compare(
    current: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]
) -> tuple[list[str], list[str]]:
    """返回 (超基线项, 可收紧项)，均为可读字符串。

    棘轮语义：只允许"存量减少"，不允许"新增"；减少时给 WARN 提示收紧基线，
    但不阻断（避免修一处就要求同步刷新基线）。
    """
    exceeded: list[str] = []
    tightenable: list[str] = []
    for kind in ("pass", "return", "debug"):
        cur = current.get(kind, {})
        base = baseline.get(kind, {})
        for file in sorted(set(cur) | set(base)):
            delta = cur.get(file, 0) - base.get(file, 0)
            if delta > 0:
                exceeded.append(f"{kind}: {file} {base.get(file, 0)} → {cur.get(file, 0)} (+{delta})")
            elif delta < 0:
                tightenable.append(f"{kind}: {file} {base.get(file, 0)} → {cur.get(file, 0)} ({delta})")
    return exceeded, tightenable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G-050 静默吞错棘轮门禁")
    parser.add_argument("--root", default=str(ROOT), help="扫描根目录（测试用）")
    parser.add_argument("--emit", action="store_true", help="打印当前统计的基线 JSON")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    current = scan(root)

    if args.emit:
        print(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if not BASELINE.exists():
        # 没有基线就无法判断"新增"，直接阻断（不允许默默关掉棘轮）
        print(f"FAIL: 基线文件不存在: {BASELINE}")
        return 1
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    exceeded, tightenable = compare(current, baseline)
    total = {kind: sum(v.values()) for kind, v in current.items()}
    print(
        f"G-050: pass={total['pass']} return={total['return']} debug={total['debug']} "
        f"(基线 pass={sum(baseline.get('pass', {}).values())} "
        f"return={sum(baseline.get('return', {}).values())} "
        f"debug={sum(baseline.get('debug', {}).values())})"
    )
    for item in tightenable:
        print(f"  WARN(可收紧基线): {item}")
    if exceeded:
        print(f"\nFAIL: {len(exceeded)} 处新增静默吞错（超出基线）")
        for item in exceeded:
            print(f"  {item}")
        return 1
    print("PASS: 无新增静默吞错")
    return 0


if __name__ == "__main__":
    sys.exit(main())
