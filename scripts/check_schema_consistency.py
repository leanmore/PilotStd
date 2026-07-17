#!/usr/bin/env python3
"""Schema 一致性检查：扫描 tests/ 中的 CREATE TABLE 语句，与迁移链对照。

通过真实 Database 运行迁移链获取生产 Schema，然后扫描 tests/ 目录下
所有 .py 文件中的 CREATE TABLE 语句，对比列定义是否一致。

不一致类型：
- EXTRA: 测试表有生产表没有的列（如之前 test_announce_detail.py 的 created_at）
- MISSING: 生产表有测试表没有的列（测试表可能过于简化）

警告模式：发现问题时打印警告，exit 0（不阻断 CI）。
"""

import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _build_reference_schema() -> dict[str, dict[str, str]]:
    """通过真实 Database 运行迁移链，返回 {table: {col: type}} 字典。"""
    if "SUPERUSER" not in os.environ:
        os.environ["SUPERUSER"] = "schema_checker"
    if "ADMIN_PASSWORD" not in os.environ:
        os.environ["ADMIN_PASSWORD"] = "schema_check_temp"

    sys.path.insert(0, str(ROOT))
    from pilotstd.core.db import Database

    tmpdir = tempfile.mkdtemp(prefix="schema_ref_")
    db_path = os.path.join(tmpdir, "ref.db")

    try:
        db = Database(db_path)
        conn = db._get_conn()

        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != '_schema_version'"
        ).fetchall()

        schema: dict[str, dict[str, str]] = {}
        for (table_name,) in rows:
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            schema[table_name] = {col[1]: col[2] for col in cols}

        db.close()
        return schema
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _extract_create_tables(filepath: Path) -> list[tuple[int, str, dict[str, str]]]:
    """从测试文件中提取 CREATE TABLE 语句，返回 [(行号, 表名, {列: 类型})]。

    使用状态机处理多行 CREATE TABLE 语句。
    """
    results: list[tuple[int, str, dict[str, str]]] = []
    try:
        text = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return results

    # 匹配 CREATE TABLE [IF NOT EXISTS] name ( ... )
    # 使用非贪婪匹配处理多行
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)\s*;?",
        re.IGNORECASE | re.DOTALL,
    )

    for m in pattern.finditer(text):
        table_name = m.group(1)
        body = m.group(2)
        lineno = text[: m.start()].count("\n") + 1

        # 提取列定义：col_name TYPE [options], ...
        columns: dict[str, str] = {}
        col_pattern = re.compile(
            r"(\w+)\s+(TEXT|INTEGER|REAL|BLOB|NUMERIC|BOOLEAN|DATETIME|JSON)(?:\s+(?:PRIMARY\s+KEY|NOT\s+NULL|UNIQUE|DEFAULT\s+\S+|AUTOINCREMENT))*",
            re.IGNORECASE,
        )

        for cm in col_pattern.finditer(body):
            col_name = cm.group(1)
            col_type = cm.group(2).upper()
            # 跳过约束关键字误匹配
            if col_name.upper() in (
                "PRIMARY",
                "FOREIGN",
                "UNIQUE",
                "CHECK",
                "CONSTRAINT",
                "CREATE",
                "TABLE",
                "INDEX",
                "KEY",
                "REFERENCES",
            ):
                continue
            columns[col_name] = col_type

        if columns:
            results.append((lineno, table_name, columns))

    return results


def _check_file(filepath: Path, ref_schema: dict[str, dict[str, str]]) -> list[tuple[int, str, str, str]]:
    """检查单个测试文件，返回不一致列表 [(行号, 表名, 类型, 详情)]。"""
    issues: list[tuple[int, str, str, str]] = []
    tables = _extract_create_tables(filepath)

    for lineno, table_name, test_columns in tables:
        if table_name not in ref_schema:
            continue

        ref_columns = ref_schema[table_name]

        # 测试表有但生产表没有的列（EXTRA — 严重问题）
        extra = set(test_columns) - set(ref_columns)
        for col in sorted(extra):
            issues.append(
                (
                    lineno,
                    table_name,
                    "EXTRA",
                    f"{col} (测试表有，生产表无)",
                )
            )

        # 生产表有但测试表没有的列（MISSING — 可能是有意省略）
        missing = set(ref_columns) - set(test_columns)
        for col in sorted(missing):
            issues.append(
                (
                    lineno,
                    table_name,
                    "MISSING",
                    f"{col} (生产表有，测试表无)",
                )
            )

    return issues


def main() -> int:
    print("=" * 60)
    print("Schema 一致性检查")
    print("=" * 60)

    # 构建参考 Schema
    print("构建参考 Schema（迁移链）...")
    try:
        ref_schema = _build_reference_schema()
        print(f"  生产表: {len(ref_schema)}, 列: {sum(len(c) for c in ref_schema.values())}")
    except Exception as e:
        print(f"  FAIL: {e}")
        return 0

    # 扫描测试文件
    tests_dir = ROOT / "tests"
    py_files = list(tests_dir.rglob("*.py"))
    print(f"扫描测试文件: {len(py_files)}")

    all_issues: dict[tuple[str, str], list[tuple[int, str, str]]] = defaultdict(list)
    files_with_creates = 0

    for fpath in sorted(py_files):
        rel = fpath.relative_to(ROOT)
        issues = _check_file(fpath, ref_schema)
        if issues:
            files_with_creates += 1
            for lineno, table, issue_type, detail in issues:
                key = (str(rel), table)
                all_issues[key].append((lineno, issue_type, detail))

    # 输出
    print()
    if all_issues:
        print(f"发现 {len(all_issues)} 处不一致（{files_with_creates} 个文件）:")
        for (file, table), problems in sorted(all_issues.items()):
            print(f"  [{file}] {table}:")
            for lineno, itype, detail in problems:
                tag = "!!" if itype == "EXTRA" else "--"
                print(f"    L{lineno}: {tag} {itype} — {detail}")

        extras = sum(1 for v in all_issues.values() for _, it, _ in v if it == "EXTRA")
        missing = sum(1 for v in all_issues.values() for _, it, _ in v if it == "MISSING")
        print()
        print("=" * 60)
        print(f"汇总: EXTRA={extras} (严重), MISSING={missing} (提示)")
        print("警告: 请逐步修复上述不一致（不阻断 CI）。")
    else:
        print("=" * 60)
        print("汇总: 0 处不一致")
        print("PASS: 测试表结构与生产 Schema 一致。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
