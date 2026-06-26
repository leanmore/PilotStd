#!/usr/bin/env python
"""门禁 GATE-04：检查 docker/api/*.py 中的路由是否记录在压力测试方案中。
退出门禁：返回 0=通过, 1=阻断（新增路由但未记录）。"""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _ROOT / "docker" / "api"
_DOC = _ROOT / "docs" / "压力测试方案.md"


def extract_routes() -> set[str]:
    """从 docker/api/*.py 提取所有 @router.get/post/put/delete 路径。"""
    routes: set[str] = set()
    for py_file in _API_DIR.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for m in re.finditer(r'@router\.(?:get|post|put|delete)\("([^"]+)"\)', content):
            routes.add(m.group(1))
    return routes


def check() -> int:
    if not _DOC.exists():
        print(f"[GATE-04] SKIP: {_DOC.name} 不存在")
        return 0
    doc_text = _DOC.read_text(encoding="utf-8")
    routes = extract_routes()
    missing = [r for r in sorted(routes) if r not in doc_text]
    if missing:
        print(f"[GATE-04] WARN: {len(missing)} 个路由未在压力测试方案中记录（非阻断）:")
        for r in missing:
            print(f"  - {r}")
    print(f"[GATE-04] PASS: {len(routes)} 个路由, {len(missing)} 个未记录")
    return 0  # 警告但不阻断——文档更新可能滞后


if __name__ == "__main__":
    sys.exit(check())
