#!/usr/bin/env python
"""门禁 GATE-01：检查 /inbox 和 /standards 在允许路径列表中。
退出门禁：返回 0=通过, 1=阻断。"""

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_GUARD = _ROOT / "pilotstd" / "core" / "path_guard.py"
_REQUIRED = {"/inbox", "/standards"}


def check() -> int:
    src = _GUARD.read_text(encoding="utf-8")
    tree = ast.parse(src)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_DOCKER_EXTRA_ROOTS":
                    if isinstance(node.value, ast.List):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                found.add(elt.value)
    missing = _REQUIRED - found
    if missing:
        print(f"[GATE-01] FAIL: {_GUARD.name} 缺少路径: {missing}")
        return 1
    print(f"[GATE-01] PASS: {_GUARD.name} 包含 {_REQUIRED}")
    return 0


if __name__ == "__main__":
    sys.exit(check())
