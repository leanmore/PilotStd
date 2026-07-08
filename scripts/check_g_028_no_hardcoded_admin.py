#!/usr/bin/env python3
"""G-028: 禁止硬编码 'admin' 作为超级管理员标识 — 前后端统一检查（合并原 GATE-11 + GATE-13）"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = ["web/src", "pilotstd", "docker", "scripts"]

# ── 通用模式（前后端通用）──────────────────────────────
_COMMON_PATTERNS: list[tuple[str, str, set[str]]] = [
    ("role === 'admin'", r"role\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js", ".py"}),
    ("username === 'admin'", r"username\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js", ".py"}),
    ("user.role === 'admin'", r"user\.role\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js", ".py"}),
    ("user['role'] 硬编码", r"user\s*\[['\"]role['\"]\]\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js", ".py"}),
]

# ── 后端专用 ──────────────────────────────────────────
_BACKEND_PATTERNS: list[tuple[str, str, set[str]]] = [
    ("SQL INSERT 硬编码 admin", r"VALUES\s*\([^)]*['\"]admin['\"]", {".py", ".sh"}),
    ("常量定义 ADMIN_ROLE = 'admin'", r"ADMIN_ROLE\s*=\s*['\"]admin['\"]", {".py"}),
]

# ── 前端专用（原 GATE-13）──────────────────────────────
_FRONTEND_PATTERNS: list[tuple[str, str, set[str]]] = [
    ("SUPERUSER_USERNAME = 'admin'", r"SUPERUSER_USERNAME\s*=\s*['\"]admin['\"]", {".vue", ".ts", ".js"}),
    ("superuserUsername = 'admin'", r"superuserUsername\s*=\s*['\"]admin['\"]", {".vue", ".ts", ".js"}),
    (
        "含 superuser 的变量 = 'admin'",
        r"(?:const|let|var)\s+.*[Ss][Uu][Pp][Ee][Rr][Uu][Ss][Ee][Rr].*\s*=\s*['\"]admin['\"]",
        {".vue", ".ts", ".js"},
    ),
    (
        "superuser 变量默认值 'admin'",
        r"[Ss][Uu][Pp][Ee][Rr][Uu][Ss][Ee][Rr].*\|\|\s*['\"]admin['\"]",
        {".vue", ".ts", ".js"},
    ),
    ("用户名常量 'admin' 用于权限判断", r"(?:USERNAME|user_name)\s*=\s*['\"]admin['\"]", {".vue", ".ts", ".js"}),
]

EXCLUDE_DIRS = {"node_modules", "dist", ".git", "__pycache__", ".pytest_cache", ".venv", "venv"}


def _is_comment(line: str, ext: str) -> bool:
    s = line.lstrip()
    if not s:
        return True
    if ext in {".py", ".sh", ".yaml", ".yml", ".toml"}:
        return s.startswith("#")
    if ext in {".js", ".ts", ".vue"}:
        return s.startswith("//") or s.startswith("/*") or s.startswith("*")
    return False


def _is_docstring_line(line: str, in_docstring: bool) -> tuple[bool, bool]:
    """追踪 Python 三引号文档字符串。返回 (当前行是文档字符串, 新状态)。"""
    count = line.count('"""') + line.count("'''")
    if count % 2 == 1:
        return in_docstring, not in_docstring
    return in_docstring, in_docstring


def main() -> int:
    found = 0
    self_name = Path(__file__).name
    for search_dir in SEARCH_DIRS:
        dir_path = ROOT / search_dir
        if not dir_path.exists():
            continue
        for file_path in dir_path.rglob("*"):
            if any(p in file_path.parts for p in EXCLUDE_DIRS):
                continue
            ext = file_path.suffix
            if ext not in {".vue", ".ts", ".js", ".py", ".sh", ".yaml", ".yml", ".toml"}:
                continue
            if file_path.name == self_name:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            in_docstring = False  # Python 三引号文档字符串追踪
            for i, line in enumerate(lines, 1):
                # 跳过注释和文档字符串
                if ext == ".py":
                    is_ds, in_docstring = _is_docstring_line(line, in_docstring)
                    if is_ds:
                        continue
                if _is_comment(line, ext):
                    continue
                for desc, pattern, valid_exts in _COMMON_PATTERNS + _BACKEND_PATTERNS + _FRONTEND_PATTERNS:
                    if ext not in valid_exts:
                        continue
                    m = re.search(pattern, line)
                    if not m:
                        continue
                    # 豁免: SH 中 export SUPERUSER=admin 是合法配置
                    if ext == ".sh":
                        var = re.search(r"(?:export\s+)?([A-Z_]+)\s*=\s*['\"]admin['\"]", line)
                        if var and var.group(1) in {"SUPERUSER", "SUPERUSER_USERNAME"}:
                            continue
                    # 豁免: yaml 中 SUPERUSER: admin
                    if ext in {".yaml", ".yml", ".toml"}:
                        var = re.search(r"([A-Z_]+)\s*:\s*['\"]?admin['\"]?", line)
                        if var and var.group(1) == "SUPERUSER":
                            continue
                    print(f"FAIL: {file_path.relative_to(ROOT)}:{i}: {desc} → {line.strip()}")
                    found += 1

    if found:
        print(f"G-028 FAIL: 检测到 {found} 处硬编码 'admin' 作为超级用户标识。")
        print("权限判断必须基于配置常量 (SUPERUSER_USERNAME)，不可硬编码字面量。")
        return 1

    print("G-028 PASS: 未发现硬编码 'admin' 权限判断。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
