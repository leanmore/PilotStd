#!/usr/bin/env python3
"""预提交钩子：检查暂存区中是否新增了 Mixin 类定义。

规则：优先使用组合模式替代 Mixin。若确需新增 Mixin，请在 PR 描述中说明原因。
"""

import re
import subprocess
import sys


def get_staged_py_files() -> list[str]:
    """获取本次提交中新增或修改的 .py 文件"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A", "--", "*.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f.endswith(".py")]


def check_mixin_in_file(file_path: str) -> list[str]:
    """检查文件中是否定义了新的 Mixin 类"""
    violations: list[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # 匹配类定义中包含 Mixin 后缀的类
            matches = re.findall(r"class\s+(\w*Mixin\w*)\s*[(:]", content)
            if matches:
                for mixin in matches:
                    violations.append(f"{file_path}: 定义了 Mixin 类 '{mixin}'")
    except OSError:
        pass
    return violations


def main() -> int:
    files = get_staged_py_files()
    if not files:
        print("[INFO] 无暂存 Python 文件，跳过 Mixin 检查")
        return 0

    all_violations: list[str] = []
    for f in files:
        all_violations.extend(check_mixin_in_file(f))

    if all_violations:
        print("\n[FAIL] 检测到新增或修改的 Mixin 类：")
        for v in all_violations:
            print(f"  - {v}")
        print("\n[HINT] 建议：请优先使用组合模式（Helper 类或工具函数）替代 Mixin。")
        print("   如需使用 Mixin，请在 PR 描述中说明原因。")
        return 1

    print("[PASS] 未检测到新增 Mixin，请继续保持。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
