#!/usr/bin/env python3
"""
同步测试文件中的 CREATE TABLE 语句与生产迁移链保持一致。

依赖：通过真实 Database 运行迁移链获取生产 Schema，
然后扫描 tests/ 目录下 .py 文件中的 CREATE TABLE 语句，
替换为与生产一致的列定义。

用法：
    python scripts/sync_test_schema.py --dry-run   # 预览变更，不写入文件
    python scripts/sync_test_schema.py             # 实际写入
"""

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _build_reference_schema() -> dict[str, list[tuple]]:
    """通过真实 Database 运行迁移链，返回 {table: [(name, type, notnull, dflt_value, pk), ...]}。"""
    if "SUPERUSER" not in os.environ:
        os.environ["SUPERUSER"] = "schema_sync"
    if "ADMIN_PASSWORD" not in os.environ:
        os.environ["ADMIN_PASSWORD"] = "schema_sync_temp"

    sys.path.insert(0, str(ROOT))
    from pilotstd.core.db import Database

    tmpdir = tempfile.mkdtemp(prefix="schema_sync_")
    db_path = os.path.join(tmpdir, "ref.db")

    try:
        db = Database(db_path)
        conn = db._get_conn()

        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != '_schema_version'"
            " ORDER BY name"
        ).fetchall()

        schema: dict[str, list[tuple]] = {}
        for (table_name,) in rows:
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            schema[table_name] = [(col[1], col[2], col[3], col[4], col[5]) for col in cols]

        db.close()
        return schema
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _generate_create_table(table_name: str, columns: list[tuple]) -> str:
    """根据列信息生成 CREATE TABLE IF NOT EXISTS DDL。"""
    col_defs = []
    for name, col_type, notnull, dflt_value, pk in columns:
        parts = [name, col_type.upper()]
        if notnull and pk == 0:
            parts.append("NOT NULL")
        if dflt_value is not None:
            val = str(dflt_value)
            if not (val.startswith("'") or val.startswith('"') or val.isdigit() or val.replace(".", "").isdigit()):
                val = f"'{val}'"
            parts.append(f"DEFAULT {val}")
        col_defs.append("    " + " ".join(parts))

    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(col_defs) + "\n);"


def _find_create_table_matches(content: str) -> list[tuple[int, int, str]]:
    """扫描所有 CREATE TABLE 语句，正确处理嵌套括号（如 PRIMARY KEY(...)）。
    返回 [(start, end, table_name), ...] 按出现顺序排列。"""
    start_pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(",
        re.IGNORECASE,
    )
    matches: list[tuple[int, int, str]] = []

    for m in start_pattern.finditer(content):
        table_name = m.group(1)
        depth = 1
        pos = m.end()
        while pos < len(content) and depth > 0:
            ch = content[pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            pos += 1

        # 现在指向匹配闭括号之后的位置
        end = pos
        # 跳过尾部的空白和分号
        while end < len(content) and content[end] in (" ", "\t", "\n", "\r", ";"):
            end += 1

        matches.append((m.start(), end, table_name))

    return matches


def _fix_file(content: str, ref_schema: dict[str, list[tuple]]) -> tuple[str, int, list[str]]:
    """在文件内容中查找并替换所有 CREATE TABLE 语句。返回 (new_content, changes, log)。"""
    log: list[str] = []

    matches = _find_create_table_matches(content)
    if not matches:
        return content, 0, log

    changes = 0
    result = content

    # 从后往前替换（避免位置偏移）
    for start, end, table_name in reversed(matches):
        if table_name not in ref_schema:
            continue

        new_ddl = _generate_create_table(table_name, ref_schema[table_name])
        old_text = content[start:end]

        if old_text.strip() == new_ddl.strip():
            continue

        result = result[:start] + new_ddl + result[end:]
        changes += 1
        log.append(f"  {table_name}: 已更新 ({len(old_text)} → {len(new_ddl)} 字符)")

    return result, changes, log


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("测试 Schema 同步工具")
    print("=" * 60)

    # 构建参考
    print("构建参考 Schema（迁移链）...")
    try:
        ref_schema = _build_reference_schema()
        total_cols = sum(len(c) for c in ref_schema.values())
        print(f"  生产表: {len(ref_schema)}, 列: {total_cols}")
        for tname, cols in sorted(ref_schema.items()):
            print(f"    {tname}: {len(cols)} 列")
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1

    # 扫描测试文件
    tests_dir = ROOT / "tests"
    py_files = sorted(tests_dir.rglob("*.py"))
    print(f"\n扫描测试文件: {len(py_files)}")

    total_changes = 0
    files_changed = 0

    for fpath in py_files:
        try:
            content = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        new_content, changes, log = _fix_file(content, ref_schema)
        if changes > 0:
            rel = fpath.relative_to(ROOT)
            print(f"\n  [{rel}]")
            for line in log:
                print(line)
            total_changes += changes
            files_changed += 1
            if not dry_run:
                fpath.write_text(new_content, encoding="utf-8")

    print()
    print("=" * 60)
    if dry_run:
        print(f"[DRY RUN] 将修改 {files_changed} 个文件, {total_changes} 处替换")
    else:
        print(f"已修改 {files_changed} 个文件, {total_changes} 处替换")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
