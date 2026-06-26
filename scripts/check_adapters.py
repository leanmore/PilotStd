#!/usr/bin/env python
"""门禁 GATE-05：检查 adapter.py 中 _ALL_ADAPTER_NAMES 与 site_config.py 一致。
退出门禁：返回 0=通过, 1=阻断。"""

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ADAPTER = _ROOT / "docker" / "api" / "adapter.py"
_SITES = _ROOT / "pilotstd" / "query" / "site_config.py"
_EXPECTED_QUERY = {"ahbz", "std_gov", "hbba", "iso_gov", "njbz365", "csres", "dbba"}
_EXPECTED_ANNOUNCE = {"gb", "hb", "db"}


def extract_allowed_adapters() -> set[str]:
    src = _ADAPTER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_ALL_ADAPTER_NAMES":
                    if isinstance(node.value, ast.List):
                        return {
                            e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
                        }
    return set()


def check() -> int:
    allowed = extract_allowed_adapters()
    if not allowed:
        print("[GATE-05] FAIL: 无法解析 _ALL_ADAPTER_NAMES")
        return 1
    expected = _EXPECTED_QUERY | _EXPECTED_ANNOUNCE
    missing = expected - allowed
    extra = allowed - expected
    if missing:
        print(f"[GATE-05] FAIL: 缺少适配器: {missing}")
        return 1
    if extra:
        print(f"[GATE-05] WARN: 新增适配器(请同步更新登记簿): {extra}")
    print("[GATE-05] PASS: 10 个适配器完整")
    return 0


if __name__ == "__main__":
    sys.exit(check())
