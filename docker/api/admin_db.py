# docker/api/admin_db.py — Admin 数据库操作 API（安全查询/修改，sqlparse AST 校验）
"""Admin 数据库操作 API：SQL 安全校验 + 执行 + 审计，仅 admin 角色可访问。"""

import logging
import sqlite3 as _sqlite3
import time as _time
from typing import Any

import sqlparse
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel
from sqlparse.tokens import DDL, DML, Keyword

from docker.auth import require_role
from pilotstd.core.audit import write_audit
from pilotstd.core.config import get_db_path

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-db"])

# ── 白名单表 ──────────────────────────────────────────────
_ALLOWED_TABLES = frozenset(
    [
        "standards",
        "favorites",
        "notification_log",
        "task_execution_history",
        "users",
        "user_preferences",
    ]
)

# ── 请求模型 ──────────────────────────────────────────────


class DbQueryRequest(BaseModel):
    """Admin 数据库操作请求体：SQL + 参数化值 + 超时 + 危险操作确认。"""

    sql: str
    params: list[Any] = []
    timeout: int = 30
    confirm_dangerous: bool = False


# ── sqlparse AST 校验工具 ─────────────────────────────────


def _get_stmt_type(parsed: Any) -> str | None:
    """从 sqlparse 解析结果中提取语句类型（基于 AST token 类型）。"""
    for token in parsed.tokens:
        if token.ttype in (DML, DDL):
            val = token.value.upper()
            for kw in ("SELECT", "DELETE", "UPDATE", "INSERT", "DROP", "CREATE", "ALTER"):
                if val.startswith(kw):
                    return kw
            return val.split()[0] if val else None
        if token.ttype is Keyword and token.value.upper() in ("DROP", "CREATE", "ALTER", "INSERT"):
            return token.value.upper()
    return None


def _has_where_clause(parsed: Any) -> bool:
    """检查 AST 中是否存在 WHERE 子句节点（递归遍历 token 树）。"""
    from sqlparse.sql import Where

    def _walk(tokens):
        """递归遍历 token 树查找 Where 节点。"""
        for token in tokens:
            if isinstance(token, Where):
                return True
            if hasattr(token, "tokens") and token.tokens:
                if _walk(token.tokens):
                    return True
        return False

    return _walk(parsed.tokens)


def _has_limit_clause(parsed: Any) -> bool:
    """检查 SELECT 是否有 LIMIT 子句。"""
    for token in parsed.flatten():
        if token.ttype is Keyword and token.value.upper() == "LIMIT":
            return True
    return False


def _extract_table_names(parsed: Any) -> set[str]:
    """从 AST 中提取引用的表名（用于白名单校验）。"""
    tables: set[str] = set()
    for token in parsed.flatten():
        if hasattr(token, "ttype") and token.ttype is sqlparse.tokens.Name:
            name = token.value.strip("`\"'[]")
            tables.add(name)
    return tables


def _validate_sql(parsed: Any, confirm_dangerous: bool) -> tuple[bool, str]:
    """SQL 安全校验（AST 级别）。返回 (通过, 错误信息)。"""
    stmt_type = _get_stmt_type(parsed)
    sql_upper = str(parsed).upper()

    # DROP DATABASE → 无条件拒绝
    if stmt_type == "DROP" and "DATABASE" in sql_upper:
        return False, "DROP DATABASE 不允许执行"

    # DROP TABLE
    if stmt_type == "DROP" and "TABLE" in sql_upper:
        if not confirm_dangerous:
            return False, "DROP TABLE 必须设置 confirm_dangerous=true"
        tables = _extract_table_names(parsed)
        if tables and not tables.issubset(_ALLOWED_TABLES):
            bad = tables - _ALLOWED_TABLES
            return False, f"表不在白名单内: {', '.join(sorted(bad))}"

    # DELETE / UPDATE 必须带 WHERE
    if stmt_type in ("DELETE", "UPDATE"):
        if not _has_where_clause(parsed):
            return False, f"{stmt_type} 必须包含 WHERE 子句"

    return True, ""


def _wrap_select_limit(sql: str) -> str:
    """为 SELECT 包装子查询自动添加 LIMIT 1001。"""
    return f"SELECT * FROM ({sql}) _limited LIMIT 1001"


# ── 执行引擎（带超时保护）─────────────────────────────────


def _execute_with_timeout(
    db_path: str,
    sql: str,
    params: list[Any],
    timeout_s: int,
) -> tuple[list[dict[str, Any]], int]:
    """在独立 sqlite3 连接上执行 SQL，带 progress handler 超时保护。
    返回 (rows, elapsed_ms)。
    """
    start = _time.monotonic()
    conn = _sqlite3.connect(db_path)
    conn.row_factory = _sqlite3.Row
    conn.text_factory = str

    # Progress handler：每 1000 条 VM 指令检查一次超时
    deadline = start + timeout_s

    def _check():
        """Progress handler：每次触发检查是否超时。"""
        if _time.monotonic() > deadline:
            raise TimeoutError(f"查询超时 ({timeout_s}s)")

    conn.set_progress_handler(_check, 1000)

    try:
        cur = conn.execute(sql, tuple(params) if params else ())
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
    finally:
        conn.close()

    elapsed = int((_time.monotonic() - start) * 1000)
    return rows, elapsed


# ── API 端点 ──────────────────────────────────────────────


def _audit_and_respond(action: str, sql: str, params: list[Any], detail: dict, code: str, msg: str, status: int):
    """审计写入 + JSON 错误响应（减少端点行数）。"""
    extra = dict(detail)
    extra.update({"sql": sql, "params": params})
    write_audit(action=action, resource="/api/admin/db/query", detail=extra)
    return JSONResponse({"success": False, "error": msg, "code": code}, status_code=status)


@router.post("/query")
@require_role("admin")
def admin_db_query(req: DbQueryRequest, request: Request) -> dict[str, Any]:
    """Admin 数据库安全查询/操作端点。"""
    # Step 1: SQL 解析
    try:
        parsed = sqlparse.parse(req.sql)[0]
    except Exception as e:
        return _audit_and_respond(
            "DB_QUERY_PARSE_ERROR",
            req.sql,
            req.params,
            {"error": str(e)},
            "PARSE_ERROR",
            f"SQL 解析失败: {e}",
            400,
        )

    stmt_type = _get_stmt_type(parsed) or "UNKNOWN"

    # Step 2: 安全校验
    ok, err = _validate_sql(parsed, req.confirm_dangerous)
    if not ok:
        return _audit_and_respond(
            "DB_QUERY_DENIED",
            req.sql,
            req.params,
            {"reason": err, "stmt_type": stmt_type},
            "VALIDATION_FAILED",
            err,
            400,
        )

    # Step 3: SELECT 自动包装 LIMIT
    is_select = stmt_type == "SELECT"
    sql_to_execute = req.sql
    if is_select and not _has_limit_clause(parsed):
        sql_to_execute = _wrap_select_limit(req.sql)

    # Step 4: 执行（带超时保护）
    db_path = get_db_path()
    try:
        rows, elapsed_ms = _execute_with_timeout(db_path, sql_to_execute, req.params, req.timeout)
    except TimeoutError:
        return _audit_and_respond(
            "DB_QUERY_TIMEOUT",
            req.sql,
            req.params,
            {"timeout_s": req.timeout},
            "TIMEOUT",
            f"查询超时 ({req.timeout}s)",
            408,
        )
    except Exception as e:
        return _audit_and_respond(
            "DB_QUERY_ERROR",
            req.sql,
            req.params,
            {"error": str(e)},
            "EXECUTION_ERROR",
            f"执行失败: {e}",
            500,
        )

    # Step 5: 结果截断
    row_count = len(rows)
    truncated = False
    if is_select and row_count == 1001:
        truncated, rows, row_count = True, rows[:1000], 1000

    # Step 6: 审计
    write_audit(
        action="DB_QUERY",
        resource="/api/admin/db/query",
        detail={
            "sql": req.sql,
            "params": req.params,
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "row_count": row_count,
        },
    )

    return {
        "success": True,
        "rows": rows,
        "row_count": row_count,
        "execution_time_ms": elapsed_ms,
        "sql": req.sql,
        "truncated": truncated if is_select else None,
    }
