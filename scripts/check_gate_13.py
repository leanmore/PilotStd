#!/usr/bin/env python3
"""GATE-13: 禁止前端代码硬编码 SUPERUSER_USERNAME = 'admin' 等超级用户字面量"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = ["web/src"]

# 检测模式: (描述, 正则)
PATTERNS: list[tuple[str, str]] = [
    # 变量定义: SUPERUSER_USERNAME = 'admin' / "admin"
    ("SUPERUSER_USERNAME = 'admin'", r"SUPERUSER_USERNAME\s*=\s*['\"]admin['\"]"),
    # 变量定义: superuserUsername = 'admin'
    ("superuserUsername = 'admin'", r"superuserUsername\s*=\s*['\"]admin['\"]"),
    # const 声明: const XXX = 'admin' 且变量名含 superuser（不区分大小写）
    (
        "含 superuser 的变量 = 'admin'",
        r"(?:const|let|var)\s+.*[Ss][Uu][Pp][Ee][Rr][Uu][Ss][Ee][Rr].*\s*=\s*['\"]admin['\"]",
    ),
    # 三元/默认值: 'admin' 作为 superuser 回退值
    ("superuser 变量默认值 'admin'", r"[Ss][Uu][Pp][Ee][Rr][Uu][Ss][Ee][Rr].*\|\|\s*['\"]admin['\"]"),
    # 'admin' 作为唯一用户名常量直接比较
    ("用户名常量 'admin' 用于权限判断", r"(?:USERNAME|user_name)\s*=\s*['\"]admin['\"]"),
]

EXCLUDE_DIRS = {"node_modules", "dist", ".git", "__pycache__", ".pytest_cache"}
EXCLUDE_FILES = {"check_gate_13.py"}


def _is_comment_line(line: str, ext: str) -> bool:
    stripped = line.lstrip()
    if not stripped:
        return True
    if ext in {".ts", ".js", ".vue"}:
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            return True
    return False


def main() -> int:
    found = 0
    for search_dir in SEARCH_DIRS:
        dir_path = ROOT / search_dir
        if not dir_path.exists():
            continue
        for file_path in dir_path.rglob("*"):
            if any(p in file_path.parts for p in EXCLUDE_DIRS):
                continue
            ext = file_path.suffix
            if ext not in {".vue", ".ts", ".js"}:
                continue
            if file_path.name in EXCLUDE_FILES:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines, 1):
                if _is_comment_line(line, ext):
                    continue
                for desc, pattern in PATTERNS:
                    if re.search(pattern, line):
                        print(f"FAIL: {file_path.relative_to(ROOT)}:{i}: {desc} → {line.strip()}")
                        found += 1

    if found:
        print(
            f"\nGATE-13 FAIL: 检测到 {found} 处硬编码 'admin' 作为超级用户标识。"
            "\n请将 SUPERUSER_USERNAME 改为:"
            "\n  const SUPERUSER_USERNAME = import.meta.env.VITE_SUPERUSER_NAME || 'SUPERUSER'"
        )
        return 1

    print("GATE-13 PASS: 前端代码未硬编码 'admin' 作为超级用户标识。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
