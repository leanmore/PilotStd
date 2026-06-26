#!/usr/bin/env python
"""门禁 GATE-02：检查 PROGRESS_TAG 等关键日志标签未被移除。
退出门禁：返回 0=通过, 1=阻断。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# (文件, 必须存在的标签/模式)
_CHECKS = [
    (_ROOT / "pilotstd" / "query" / "engine.py", "PROGRESS_TAG"),
    (_ROOT / "pilotstd" / "query" / "engine.py", "[CACHE]"),
    (_ROOT / "tests" / "stress_driver.py", "PROGRESS_TAG"),
    (_ROOT / "tests" / "test_observability.py", "PROGRESS_TAG"),
]


def check() -> int:
    failed = 0
    for path, tag in _CHECKS:
        if not path.exists():
            print(f"[GATE-02] SKIP: {path.name} 不存在")
            continue
        content = path.read_text(encoding="utf-8")
        if tag not in content:
            print(f"[GATE-02] FAIL: {tag} 在 {path.name} 中缺失")
            failed += 1
    if failed:
        print(f"[GATE-02] FAIL: {failed} 项检查失败")
        return 1
    print("[GATE-02] PASS: 关键日志标签完好")
    return 0


if __name__ == "__main__":
    sys.exit(check())
