#!/usr/bin/env python3
"""GATE-12: 检查 Vue 组件是否显式声明 defineOptions，防止生产构建中组件名被压缩器删除"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = ["web/src/components", "web/src/views"]


def main() -> int:
    failed: list[str] = []
    for dir_name in SEARCH_DIRS:
        search_dir = ROOT / dir_name
        if not search_dir.exists():
            continue
        for vue_file in sorted(search_dir.rglob("*.vue")):
            content = vue_file.read_text(encoding="utf-8")
            if "<script setup" not in content:
                continue
            if "defineOptions" not in content:
                failed.append(str(vue_file))

    if failed:
        print(f"GATE-12 FAIL: {len(failed)} 个 <script setup> 组件缺少 defineOptions:")
        for f in failed:
            print(f"  - {f}")
        print("请在 <script setup> 第一行添加：defineOptions({{ name: '组件名' }})")
        return 1

    print("GATE-12 PASS: 所有 <script setup> 组件均已声明 defineOptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
