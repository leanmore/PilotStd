#!/usr/bin/env python3
"""
G-038: 历史遗留错误清零
运行 Ruff 和 Mypy 全量扫描，发现任何错误即阻断。
禁止使用 # noqa 或 --add-noqa 静默历史错误。
执行者必须当场修复代码，确保零错误后方可继续提交流程。
"""

import subprocess
import sys
from pathlib import Path

# 控制台-8编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 扫描范围
SCAN_TARGETS = ["pilotstd/", "tests/", "scripts/"]


def run_ruff() -> tuple[bool, str]:
    """运行 Ruff 检查，返回 (是否通过, 输出内容)"""
    try:
        result = subprocess.run(
            ["ruff", "check", *SCAN_TARGETS],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=120,
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, "ruff 未安装，请执行: pip install ruff"
    except subprocess.TimeoutExpired:
        return False, "ruff 检查超时（120s）"


def run_mypy() -> tuple[bool, str]:
    """运行 Mypy 检查，返回 (是否通过, 输出内容)"""
    try:
        result = subprocess.run(
            ["mypy", *SCAN_TARGETS],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=180,
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, "mypy 未安装，请执行: pip install mypy"
    except subprocess.TimeoutExpired:
        return False, "mypy 检查超时（180s）"


def check_noqa_suppression() -> tuple[bool, str]:
    """检查是否存在通过 # noqa 静默错误的行为"""
    noqa_files: list[str] = []
    for target in SCAN_TARGETS:
        target_path = PROJECT_ROOT / target
        if not target_path.exists():
            continue
        for py_file in target_path.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "# noqa" in content:
                # 统计数量
                count = content.count("# noqa")
                noqa_files.append(f"  {py_file.relative_to(PROJECT_ROOT)} ({count} 处)")

    if noqa_files:
        msg = (
            "发现 # noqa 静默注释，G-038 禁止使用此方式绕过检查：\n"
            + "\n".join(noqa_files)
            + "\n请修复根因后移除 # noqa 注释。"
        )
        return False, msg

    return True, ""


def main() -> int:
    errors: list[str] = []

    # 1.检查
    ruff_passed, ruff_output = run_ruff()
    if not ruff_passed:
        errors.append(f"Ruff 检查失败：\n{ruff_output}")

    # 2.检查
    mypy_passed, mypy_output = run_mypy()
    if not mypy_passed:
        errors.append(f"Mypy 检查失败：\n{mypy_output}")

    # 3.静默检查
    noqa_passed, noqa_output = check_noqa_suppression()
    if not noqa_passed:
        errors.append(noqa_output)

    if errors:
        print("❌ G-038 历史遗留错误清零检查失败：")
        for err in errors:
            print(err)
            print()
        print("执行者必须当场修复所有错误，禁止跳过。")
        return 1

    print("✅ G-038 通过：Ruff 零错误、Mypy 零错误、无 # noqa 静默")
    return 0


if __name__ == "__main__":
    sys.exit(main())
