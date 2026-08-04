#!/usr/bin/env python3
"""STATUS.md 自动更新 — 从测试/门禁提取数据，刷新统计字段。

仅更新可自动获取的统计字段（测试数、G-010 违规数、日期），
手动填写的字段（关键决策、治理动作等）保留不动。
本地使用，不入 CI。
"""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = ROOT / "STATUS.md"


def count_python_tests() -> str:
    """运行 pytest --collect-only -q 提取测试统计。"""
    try:
        result = subprocess.run(
            ["pytest", "--collect-only", "-q", "--no-header"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60,
        )
        for line in result.stdout.splitlines():
            m = re.search(r"(\d+)\s+tests?\s+collected", line)
            if m:
                return f"{m.group(1)} collected"
        return "解析失败，请手动检查"
    except Exception:
        return "解析失败，请手动检查"


def count_frontend_tests() -> str:
    """运行 vitest run 并解析 JSON reporter 输出获取测试数。"""
    try:
        result = subprocess.run(
            ["npx", "vitest", "run", "--reporter=json"],
            capture_output=True,
            text=True,
            cwd=ROOT / "web",
            timeout=120,
        )
        import json as _json

        try:
            data = _json.loads(result.stdout.strip())
            total = data.get("numTotalTests", 0)
            passed = data.get("numPassedTests", 0)
            failed = data.get("numFailedTests", 0)
            return f"{passed} passed / {failed} failed / {total} total"
        except (_json.JSONDecodeError, AttributeError):
            pass
        # 回退：统计测试文件数
        test_dir = ROOT / "web" / "src"
        count = len(list(test_dir.rglob("*.test.*"))) + len(list(test_dir.rglob("*.spec.*")))
        return f"{count} test files" if count > 0 else "解析失败，请手动检查"
    except Exception:
        return "解析失败，请手动检查"


def count_g010_violations() -> str:
    """运行 G-010 提取违规数。"""
    try:
        result = subprocess.run(
            ["python", "scripts/check_g_010_code_size.py"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30,
        )
        m = re.search(r"(\d+)\s*处违规", result.stdout)
        if m:
            return m.group(1)
        if "PASS" in result.stdout or "pass" in result.stdout.lower():
            return "0"
    except Exception:
        pass
    return "—"


def update_status() -> None:
    if not STATUS_PATH.exists():
        print(f"STATUS.md 不存在: {STATUS_PATH}")
        sys.exit(1)

    content = STATUS_PATH.read_text(encoding="utf-8")
    today = date.today().isoformat()

    py_tests = count_python_tests()
    fe_tests = count_frontend_tests()
    gate10 = count_g010_violations()

    # ── 更新测试通过率行 ──
    test_line = f"| 测试通过率 | Python {py_tests}，前端 {fe_tests} |"
    content = re.sub(
        r"\| 测试通过率 \|.*\|",
        test_line.replace("|", "\\|"),
        content,
    )
    content = re.sub(
        r"\| 测试通过率 \|.*\|",
        test_line,
        content,
    )

    # ──更新-010违规数──
    gate10_line = f"| G-010 违规 | {gate10} |"
    content = re.sub(
        r"\| G-010 违规 \|.*\|",
        gate10_line.replace("|", "\\|"),
        content,
    )
    content = re.sub(
        r"\| G-010 违规 \|.*\|",
        gate10_line,
        content,
    )

    # ── 更新最后更新日期 ──
    content = re.sub(
        r"> 本地状态文件，不入仓库。最后更新：\d{4}-\d{2}-\d{2}",
        f"> 本地状态文件，不入仓库。最后更新：{today}",
        content,
    )

    STATUS_PATH.write_text(content, encoding="utf-8")
    print("[update_status] STATUS.md 已更新")
    print(f"  测试: Python {py_tests} | 前端 {fe_tests}")
    print(f"  G-010 违规: {gate10}")
    print(f"  日期: {today}")


if __name__ == "__main__":
    update_status()
