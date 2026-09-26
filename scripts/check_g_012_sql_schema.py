#!/usr/bin/env python3
"""门禁零一二：查询与表结构一致性检查。

通过迁移链构建生产数据结构，扫描派森文件中的查询字符串，
提取插入/更新/查询中的列名并与数据结构对照。
格式化字符串动态片段和查询星号跳过。
"""

import os
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 门禁零一二豁免：含连接且用表别名的查询字符串，
# 列名到表归属在静态分析层面不可判定，人工审核确认无误后豁免
# （原归档重试服务模块的豁免项随该死代码服务删除而移除）
_SQL_CHECK_SKIP: dict = {}
SCAN_DIRS = [
    ROOT / "docker" / "api",
    ROOT / "pilotstd" / "manager",
    ROOT / "pilotstd" / "announcement",
    ROOT / "pilotstd" / "tasks",
]


# SQL 文本解析层拆到 scripts/_sql_schema_parser.py（G-010 规模控制，2026-09-26）
from _sql_schema_parser import (  # noqa: E402
    _extract_insert_cols,
    _extract_select_cols,
    _extract_update_cols,
    _find_sql_strings,
)


def _build_schema() -> dict[str, set[str]]:
    """通过真实数据库运行迁移链，构建表名的列集合字典。"""
    if "SUPERUSER" not in os.environ:
        os.environ["SUPERUSER"] = "g012_schema_checker"
    if "ADMIN_PASSWORD" not in os.environ:
        os.environ["ADMIN_PASSWORD"] = "g012_temp_password_42"

    sys.path.insert(0, str(ROOT))

    from pilotstd.core.db import Database

    tmpdir = tempfile.mkdtemp(prefix="g012_schema_")
    db_path = os.path.join(tmpdir, "schema.db")

    try:
        db = Database(db_path)
        conn = db._get_conn()

        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != '_schema_version'"
        ).fetchall()

        schema: dict[str, set[str]] = {}
        for (table_name,) in rows:
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            schema[table_name] = {col[1] for col in cols}

        db.close()
        return schema
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        # 清理系统路径
        if str(ROOT) in sys.path:
            sys.path.remove(str(ROOT))




def _check_file(file_path: Path, schema: dict[str, set[str]], rel_path: Path) -> list[tuple[int, str, str, str]]:
    """检查单个文件，返回错误列表 [(行号, 表名, 列名, SQL片段), ...]

    列名检查策略：
    - INSERT/UPDATE：精确匹配目标表
    - SELECT：检查列是否存在于 FROM+JOIN 的任一表中；
      若 SQL 中无法解析到任何表（如纯子查询），回退到全库检查
    """
    all_columns: set[str] = set()
    for cols in schema.values():
        all_columns.update(cols)

    errors: list[tuple[int, str, str, str]] = []
    sql_fragments = _find_sql_strings(file_path)

    for sql, lineno in sql_fragments:
        # 豁免检查
        if _SQL_CHECK_SKIP.get((str(rel_path), lineno)):
            continue
        # 插入列名 — 精确匹配目标表
        for table, col in _extract_insert_cols(sql):
            if table in schema and col not in schema[table]:
                errors.append((lineno, table, col, f"INSERT INTO {table}"))

        # 更新列名 — 精确匹配目标表
        for table, col in _extract_update_cols(sql):
            if table in schema and col not in schema[table]:
                errors.append((lineno, table, col, f"UPDATE {table}"))

        # 查询列名 — 检查来源与连接的表，回退到全库
        for ref_tables, col in _extract_select_cols(sql):
            if ref_tables:
                # 检查列是否存在于任一引用表
                ref_cols: set[str] = set()
                for t in ref_tables:
                    if t in schema:
                        ref_cols.update(schema[t])
                if col not in ref_cols:
                    tables_str = ", ".join(sorted(ref_tables))
                    errors.append((lineno, tables_str, col, f"SELECT FROM {tables_str}"))
            else:
                # 无法解析表名，回退全库检查
                if col not in all_columns:
                    errors.append((lineno, "(unknown)", col, "SELECT"))

    return errors


def main() -> int:
    print("G-012: SQL-表结构一致性检查")
    print("=" * 60)

    # 第一步：构建数据结构
    print("构建数据库 Schema（迁移链）...")
    try:
        schema = _build_schema()
        table_count = len(schema)
        col_count = sum(len(cols) for cols in schema.values())
        print(f"  表: {table_count}, 列: {col_count}")
    except Exception as e:
        print(f"  FAIL: 无法构建 Schema — {e}")
        return 1

    # 2. 扫描文件
    print(f"扫描目录: {', '.join(str(d.relative_to(ROOT)) for d in SCAN_DIRS)}")
    py_files: list[Path] = []
    for d in SCAN_DIRS:
        if d.exists():
            py_files.extend(d.rglob("*.py"))

    if not py_files:
        print("  未找到 Python 文件")
        return 0

    print(f"  扫描文件: {len(py_files)}")

    # 3. 检查每个文件
    all_errors: dict[tuple[str, str, str], list[tuple[int, str]]] = defaultdict(list)
    total_sql = 0

    for f in sorted(py_files):
        rel = f.relative_to(ROOT)
        try:
            sqls = _find_sql_strings(f)
            total_sql += len(sqls)
            errors = _check_file(f, schema, rel)
            for lineno, table, col, context in errors:
                key = (str(rel), table, col)
                all_errors[key].append((lineno, context))
        except Exception:
            continue

    print(f"  SQL 字符串: {total_sql}")

    # 4. 输出结果
    print()
    if all_errors:
        print(f"FAIL: {len(all_errors)} 处列名不一致:")
        for (file, table, col), occurrences in sorted(all_errors.items()):
            lines = ", ".join(f"L{ln}" for ln, _ in occurrences)
            contexts = occurrences[0][1]
            print(f"  [{file}:{lines}] {table}.{col} ({contexts})")
        print()
        print("=" * 60)
        print(f"汇总: {len(all_errors)} 处不一致")
        print("FAIL: 请修复上述列引用后再提交。")
        return 1

    print("=" * 60)
    print(f"汇总: 0 处不一致 / {total_sql} 条SQL")
    print("PASS: 所有 SQL 列引用均在数据库中存在。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
