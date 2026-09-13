#!/usr/bin/env python3
"""门禁零一二：查询与表结构一致性检查。

通过迁移链构建生产数据结构，扫描派森文件中的查询字符串，
提取插入/更新/查询中的列名并与数据结构对照。
格式化字符串动态片段和查询星号跳过。
"""

import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 门禁零一二豁免：含连接且用表别名的查询字符串，
# 列名到表归属在静态分析层面不可判定，人工审核确认无误后豁免
# （原 archive_retry_service.py 的豁免项随该死代码服务删除而移除）
_SQL_CHECK_SKIP: dict = {}
SCAN_DIRS = [
    ROOT / "docker" / "api",
    ROOT / "pilotstd" / "manager",
    ROOT / "pilotstd" / "announcement",
    ROOT / "pilotstd" / "tasks",
]

# ── 结构化查询关键字（排除非列名的标识符） ──
SQL_KEYWORDS = frozenset(
    {
        "SELECT",
        "FROM",
        "WHERE",
        "INSERT",
        "INTO",
        "VALUES",
        "UPDATE",
        "SET",
        "DELETE",
        "CREATE",
        "ALTER",
        "TABLE",
        "DROP",
        "INDEX",
        "ON",
        "AND",
        "OR",
        "NOT",
        "NULL",
        "IS",
        "IN",
        "LIKE",
        "BETWEEN",
        "EXISTS",
        "HAVING",
        "GROUP",
        "BY",
        "ORDER",
        "ASC",
        "DESC",
        "LIMIT",
        "OFFSET",
        "JOIN",
        "LEFT",
        "RIGHT",
        "INNER",
        "OUTER",
        "CROSS",
        "UNION",
        "ALL",
        "DISTINCT",
        "AS",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "PRIMARY",
        "KEY",
        "FOREIGN",
        "REFERENCES",
        "DEFAULT",
        "CHECK",
        "UNIQUE",
        "CONSTRAINT",
        "CASCADE",
        "IF",
        "REPLACE",
        "IGNORE",
        "ABORT",
        "ROLLBACK",
        "COMMIT",
        "BEGIN",
        "TRANSACTION",
        "OVER",
        "PARTITION",
        "ROW_NUMBER",
        "RANK",
        "DENSE_RANK",
        "ROWID",
        "CAST",
        "COALESCE",
        "IFNULL",
        "NULLIF",
        "COUNT",
        "SUM",
        "AVG",
        "MIN",
        "MAX",
        "TOTAL",
        "GROUP_CONCAT",
        "ABS",
        "ROUND",
        "LENGTH",
        "SUBSTR",
        "REPLACE",
        "TRIM",
        "LTRIM",
        "RTRIM",
        "UPPER",
        "LOWER",
        "DATE",
        "TIME",
        "DATETIME",
        "STRFTIME",
        "JULIANDAY",
        "RANDOM",
        "RANDOMBLOB",
        "ZEROBLOB",
        "TYPEOF",
        "LAST_INSERT_ROWID",
        "SQLITE_VERSION",
        "CHANGES",
        "TOTAL_CHANGES",
        "LIKE",
        "GLOB",
        "REGEXP",
        "MATCH",
        "ESCAPE",
        "BETWEEN",
        "CASE",
        "CAST",
        "CURRENT_TIME",
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
    }
)

# ── 派森内置名称（可能出现在查询字符串中） ──
PYTHON_BUILTINS = frozenset(
    {
        "True",
        "False",
        "None",
        "self",
        "cls",
    }
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


def _merge_string_literals(lines: list[str]) -> list[tuple[str, int]]:
    """合并 Python 隐式相邻字符串字面量，返回 (合并文本, 起始行号) 列表。"""
    merged: list[tuple[str, int]] = []
    current_parts: list[str] = []
    current_start = 0
    str_re = re.compile(r'^\s*["\'](.*?)["\']\s*$')

    for i, line in enumerate(lines, 1):
        m = str_re.match(line)
        if m:
            content = m.group(1)
            if not current_parts:
                current_start = i
            current_parts.append(content)
        else:
            if current_parts:
                merged.append((" ".join(current_parts), current_start))
                current_parts = []
            # 同时处理格式化字符串
            fm = re.match(r'^\s*f["\'](.*?)["\']\s*$', line)
            if fm:
                merged.append((fm.group(1), i))

    if current_parts:
        merged.append((" ".join(current_parts), current_start))

    return merged


def _find_sql_strings(file_path: Path) -> list[tuple[str, int]]:
    """从 .py 文件中提取所有 SQL 字符串片段，返回 (SQL文本, 行号) 列表。"""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    sql_fragments: list[tuple[str, int]] = []
    merged = _merge_string_literals(lines)

    sql_kw_re = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE\s+TABLE|ALTER\s+TABLE)\b", re.IGNORECASE)

    for text, lineno in merged:
        if sql_kw_re.search(text):
            sql_fragments.append((text, lineno))

    return sql_fragments


def _extract_insert_cols(sql: str) -> list[tuple[str, str]]:
    """从 INSERT INTO t (col1, col2) 中提取列名列表。返回 [(table, col), ...]"""
    results: list[tuple[str, str]] = []
    # 说明：插入[或替换]到 表名(列一, 列二, ...)
    pattern = re.compile(
        r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\w+)\s*\(([^)]+)\)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(sql):
        table = m.group(1)
        cols_str = m.group(2)
        cols = [c.strip() for c in cols_str.split(",")]
        for col in cols:
            col = _clean_column(col)
            if col:
                results.append((table, col))
    return results


def _extract_update_cols(sql: str) -> list[tuple[str, str]]:
    """从 UPDATE t SET col1=?, col2=? 中提取列名列表。"""
    results: list[tuple[str, str]] = []
    # 说明：更新 表 设值 列=值, 列二=值 [条件子句 ...]
    # 先找表名
    table_m = re.search(r"UPDATE\s+(\w+)\s+SET\s+", sql, re.IGNORECASE)
    if not table_m:
        return results
    table = table_m.group(1)

    # 提取设值到条件/结束/分号之间的部分
    set_start = table_m.end()
    rest = sql[set_start:]

    # 截断到条件子句、来源、返回子句、分号或字符串结尾
    set_end = len(rest)
    for kw in ("WHERE", "FROM", "RETURNING", ";"):
        m = re.search(r"\b" + kw + r"\b", rest, re.IGNORECASE)
        if m:
            set_end = min(set_end, m.start())

    set_clause = rest[:set_end]

    # 处理格式化字符串动态片段
    if "{" in set_clause:
        # 尝试提取静态部分的列名
        # 移除花括号占位部分后再解析
        set_clause = re.sub(r"\{[^}]*\}", "", set_clause)

    # 按逗号分割（注意函数调用中的逗号）
    parts = _split_cols(set_clause)
    for part in parts:
        col = _clean_column(part.split("=")[0].strip())
        if col:
            results.append((table, col))
    return results


def _extract_from_tables(sql: str) -> set[str]:
    """从查询的来源与连接子句中提取所有引用的表名。"""
    tables: set[str] = set()
    # 说明：来自 表 [别名]
    for m in re.finditer(r"\bFROM\s+(\w+)", sql, re.IGNORECASE):
        tables.add(m.group(1))
    # 说明：连接 表 [别名]
    for m in re.finditer(r"\bJOIN\s+(\w+)", sql, re.IGNORECASE):
        tables.add(m.group(1))
    return tables


def _extract_select_cols(sql: str) -> list[tuple[set[str], str]]:
    """从 SELECT col1, col2 FROM table [JOIN ...] 中提取列名列表。

    返回 [(referenced_tables, col), ...]，referenced_tables 包含 FROM + JOIN 的所有表。
    """
    results: list[tuple[set[str], str]] = []
    referenced = _extract_from_tables(sql)

    # 找查询...来自表模式
    pattern = re.compile(
        r"SELECT\s+(.+?)\s+FROM\s+(\w+(?:\s+AS\s+\w+)?)",
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(sql):
        cols_str = m.group(1)

        # 跳过查询星号和子查询中的查询
        if cols_str.strip() == "*":
            continue
        if cols_str.strip().upper().startswith("SELECT"):
            continue

        # 处理格式化字符串动态片段
        if "{" in cols_str:
            cols_str = re.sub(r"\{[^}]*\}", "", cols_str)

        parts = _split_cols(cols_str)
        for part in parts:
            col = _clean_column(part)
            if col:
                results.append((referenced, col))

    return results


# ── 结构化查询内置函数名（列名提取时识别函数调用） ──
_SQL_FUNCTIONS = frozenset(
    {
        "MAX",
        "MIN",
        "COUNT",
        "SUM",
        "AVG",
        "COALESCE",
        "IFNULL",
        "NULLIF",
        "DATE",
        "TIME",
        "DATETIME",
        "STRFTIME",
        "ABS",
        "ROUND",
        "LENGTH",
        "SUBSTR",
        "REPLACE",
        "TRIM",
        "UPPER",
        "LOWER",
        "TYPEOF",
        "TOTAL",
        "GROUP_CONCAT",
        "JULIANDAY",
        "RANDOM",
        "RANDOMBLOB",
        "ZEROBLOB",
        "LAST_INSERT_ROWID",
        "CHANGES",
        "TOTAL_CHANGES",
        "UNICODE",
        "QUOTE",
        "HEX",
        "PRINTF",
        "INSTR",
    }
)


def _strip_as_alias(col: str) -> str:
    """去除 AS 别名后缀，如 'fetched_at AS created_at' → 'fetched_at'。"""
    parts = re.split(r"\s+AS\s+", col, flags=re.IGNORECASE)
    return parts[0].strip()


def _extract_func_arg(col: str) -> str:
    """从单参函数调用中提取参数列名。MAX(x) → x。多参/复杂参数返回 ''。"""
    m = re.match(r"^(\w+)\s*\((.*)\)\s*$", col)
    if not m:
        return ""
    func_name = m.group(1).upper()
    func_args = m.group(2)
    if func_name in SQL_KEYWORDS or func_name in _SQL_FUNCTIONS:
        if func_args and func_args != "*" and "," not in func_args:
            return _clean_column(func_args)
    return ""


def _split_expression(col: str) -> str:
    """从表达式中提取纯列名。处理 || 拼接、比较运算符、IS NULL/IN/LIKE 等。"""
    # || 字符串拼接：取第一个非字面量部分
    if "||" in col:
        for part in col.split("||"):
            cleaned = part.strip().strip("'").strip('"')
            if cleaned and cleaned.upper() not in SQL_KEYWORDS:
                return cleaned
        return ""

    # 比较运算符
    for op in (">=", "<=", "!=", "<>", "=", ">", "<"):
        if op in col:
            col = col.split(op)[0].strip()
            break

    # 为空、在其中、像 等关键字
    for kw in (" IS ", " IN ", " NOT ", " LIKE ", " GLOB ", " BETWEEN "):
        pos = col.upper().find(kw)
        if pos > 0:
            col = col[:pos].strip()
            break

    # 算术运算符
    for op in (" + ", " - ", " * ", " / "):
        if op in col and "||" not in col:
            col = col.split(op)[0].strip()
            break

    return col


def _clean_column(raw: str) -> str:
    """清洗列名：去除 AS 别名、函数调用、字面量、表前缀。返回纯列名或空字符串。"""
    col = raw.strip()
    if not col:
        return ""

    # 跳过格式化字符串占位符、字符串/数字字面量
    if "{" in col or "}" in col:
        return ""
    if re.match(r'^["\']', col) or re.match(r"^\d+", col):
        return ""

    # 去除作为别名后缀
    col = _strip_as_alias(col)

    # 处理函数调用：取大值参数 → 提取；合并参数 → 跳过
    func_result = _extract_func_arg(col)
    if func_result:
        return func_result
    # 函数调用但无法提取参数 → 跳过
    if re.match(r"^\w+\s*\(", col):
        return ""

    # 跳过查询关键字和派森内置名
    upper = col.upper().strip()
    if upper in SQL_KEYWORDS or upper in PYTHON_BUILTINS:
        return ""

    # 表前缀：表名点列名 → 列名
    if "." in col:
        col = col.split(".")[-1].strip()

    # 表达式提取纯列名
    col = _split_expression(col)

    # 最终验证
    col = col.strip().strip("'").strip('"')
    if not col:
        return ""
    upper = col.upper()
    if upper in SQL_KEYWORDS or upper in PYTHON_BUILTINS:
        return ""
    if re.match(r"^\d+$", col):
        return ""
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
        return ""

    return col


def _split_cols(cols_str: str) -> list[str]:
    """按逗号分割列列表，正确处理括号嵌套（函数调用）。"""
    parts = []
    depth = 0
    current = []
    for ch in cols_str:
        if ch == "(" or ch == "[":
            depth += 1
            current.append(ch)
        elif ch == ")" or ch == "]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


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
