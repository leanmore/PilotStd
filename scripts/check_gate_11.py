#!/usr/bin/env python3
"""GATE-11: 禁止硬编码 'admin' 作为超级管理员标识 — 权限判断必须基于配置常量"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = ["web/src", "pilotstd", "docker", "scripts"]

# 检查模式: (描述, 正则, 文件扩展名过滤器)
PATTERNS = [
    # JS/TS/Vue: role === 'admin' / role == 'admin' / role !== 'admin' / role != 'admin'
    ("role === 'admin' 或 role == 'admin'", r"role\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js"}),
    # Python: role == 'admin'
    ("Python role 硬编码", r"role\s*[!=]=\s*['\"]admin['\"]", {".py"}),
    # JS/TS: username === 'admin' (前端硬编码)
    ("username === 'admin'", r"username\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js"}),
    # Python: username == 'admin'
    ("Python username 硬编码", r"username\s*[!=]=\s*['\"]admin['\"]", {".py"}),
    # user.role === 'admin'
    ("user.role === 'admin'", r"user\.role\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js", ".py"}),
    # user['role'] == 'admin'
    ("user['role'] 硬编码", r"user\s*\[['\"]role['\"]\]\s*[!=]={1,2}\s*['\"]admin['\"]", {".vue", ".ts", ".js", ".py"}),
    # SQL INSERT VALUES 含 'admin'
    ("SQL INSERT 硬编码 admin", r"VALUES\s*\([^)]*['\"]admin['\"]", {".py", ".sh"}),
    # 常量定义 ADMIN_USER = 'admin'
    ("常量定义 ADMIN_USER = 'admin'", r"ADMIN[a-zA-Z_]*\s*=\s*['\"]admin['\"]", {".py", ".ts", ".js", ".sh"}),
]

EXCLUDE_DIRS = {"node_modules", "dist", ".git", "__pycache__", ".pytest_cache", "__pycache__", ".venv", "venv"}


def _is_comment_line(line: str, ext: str) -> bool:
    stripped = line.lstrip()
    if not stripped:
        return True
    if ext in {".py", ".sh", ".yaml", ".yml", ".toml"}:
        if stripped.startswith("#"):
            return True
    if ext in {".js", ".ts", ".vue"}:
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            return True
    return False


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
            if file_path.name.endswith(".md") or file_path.name == self_name:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines, 1):
                if _is_comment_line(line, ext):
                    continue
                for desc, pattern, valid_exts in PATTERNS:
                    if ext not in valid_exts:
                        continue
                    m = re.search(pattern, line)
                    if m:
                        # 豁免：ADMIN_ROLE="admin" 常量定义（GATE-11 统一入口）
                        var_decl = re.search(r"(ADMIN_ROLE|ADMIN_USER)\s*=\s*['\"]admin['\"]", line)
                        if var_decl:
                            continue
                        # 豁免：SH 文件中 export SUPERUSER=admin 是配置
                        if ext == ".sh":
                            var_name = re.search(r"(export\s+)?([A-Z_]+)\s*=\s*['\"]admin['\"]", line)
                            if var_name and var_name.group(2) in {
                                "SUPERUSER",
                                "SUPERUSER_USERNAME",
                            }:
                                continue
                        # yaml/docker-compose 中 SUPERUSER: admin 允许
                        if ext in {".yaml", ".yml", ".toml"}:
                            var_name = re.search(r"([A-Z_]+)\s*:\s*['\"]?admin['\"]?", line)
                            if var_name and var_name.group(1) == "SUPERUSER":
                                continue
                        print(f"FAIL: {file_path}:{i}: {desc} → {line.strip()}")
                        found += 1

    if found:
        print(f"GATE-11 FAIL: 检测到 {found} 处硬编码 'admin' 权限判断。")
        return 1

    print("GATE-11 PASS: 未发现硬编码 'admin' 权限判断。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
