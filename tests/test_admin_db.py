# tests/test_admin_db.py
# Admin DB API — SQL 安全校验 + 执行 + 审计（测试覆盖 14+ 场景）

import importlib as _il
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch

# ── SQL 校验单元测试 ──────────────────────────────────────
import sqlparse as _sp


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_admin_db():
    """模块级 env 隔离：强制注入 admin_db 测试值，teardown 恢复原值。

    标准模式见 test_api_favorites_auth.py:25-38 —— 杜绝模块级 setdefault
    污染后续导入的测试模块（TD-10）。
    """
    old_values = {}
    env_vars = {
        "JWT_SECRET": "admin_db_test_secret",
        "SUPERUSER": "admin_db_test_user",
    }
    for k, v in env_vars.items():
        old_values[k] = os.environ.get(k)
        os.environ[k] = v
    yield
    for k, old in old_values.items():
        if old is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = old


def test_validate_select_ok():
    from docker.api.admin_db import _get_stmt_type, _validate_sql

    p = _sp.parse("SELECT * FROM users WHERE id=1 LIMIT 10")[0]
    assert _get_stmt_type(p) == "SELECT"
    ok, err = _validate_sql(p, False)
    assert ok, err


def test_validate_delete_no_where_rejected():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("DELETE FROM users")[0]
    ok, err = _validate_sql(p, False)
    assert not ok
    assert "WHERE" in err


def test_validate_delete_comment_bypass_rejected():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("DELETE FROM users -- where id=1")[0]
    ok, err = _validate_sql(p, False)
    assert not ok


def test_validate_delete_with_where_ok():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("DELETE FROM users WHERE id=1")[0]
    ok, err = _validate_sql(p, False)
    assert ok


def test_validate_update_no_where_rejected():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("UPDATE users SET name='x'")[0]
    ok, err = _validate_sql(p, False)
    assert not ok


def test_validate_drop_table_no_confirm():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("DROP TABLE users")[0]
    ok, err = _validate_sql(p, False)
    assert not ok
    assert "confirm_dangerous" in err


def test_validate_drop_table_whitelisted():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("DROP TABLE users")[0]
    ok, err = _validate_sql(p, True)
    assert ok, err


def test_validate_drop_table_not_whitelisted():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("DROP TABLE secret_data")[0]
    ok, err = _validate_sql(p, True)
    assert not ok
    assert "白名单" in err


def test_validate_drop_database_rejected():
    from docker.api.admin_db import _validate_sql

    p = _sp.parse("DROP DATABASE test")[0]
    ok, err = _validate_sql(p, True)
    assert not ok
    assert "DROP DATABASE" in err


def test_has_where_detection():
    from docker.api.admin_db import _has_where_clause

    assert _has_where_clause(_sp.parse("DELETE FROM t WHERE id=1")[0])
    assert not _has_where_clause(_sp.parse("DELETE FROM t -- where")[0])
    assert _has_where_clause(_sp.parse("UPDATE t SET x=1 WHERE y=2")[0])


def test_has_limit_detection():
    from docker.api.admin_db import _has_limit_clause

    assert _has_limit_clause(_sp.parse("SELECT * FROM t LIMIT 10")[0])
    assert not _has_limit_clause(_sp.parse("SELECT * FROM t")[0])


def test_wrap_select_limit():
    from docker.api.admin_db import _wrap_select_limit

    result = _wrap_select_limit("SELECT * FROM t")
    assert "LIMIT 1001" in result
    assert result.startswith("SELECT * FROM (")


def test_extract_table_names():
    from docker.api.admin_db import _extract_table_names

    tables = _extract_table_names(_sp.parse("DROP TABLE users")[0])
    assert "users" in tables


def test_timeout_progress_handler():
    from docker.api.admin_db import _execute_with_timeout

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    import sqlite3 as _sqlite3

    conn = _sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    try:
        rows, _ = _execute_with_timeout(db_path, "SELECT * FROM t", [], 1)
    except TimeoutError:
        pass

    os.unlink(db_path)


# ── API 端点集成测试 ─────────────────────────────────────


def _reload_admin_db():
    """重新加载 admin_db 模块，返回 router。"""
    import docker.api.admin_db as _adm

    _il.reload(_adm)
    return _adm.router


@patch("docker.auth.require_role", lambda role: lambda f: f)
def test_api_select_returns_data(tmp_path):
    db_path = str(tmp_path / "api_test.db")
    import sqlite3 as _sqlite3

    conn = _sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        must_change_password INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    )""")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, salt, role) "
        "VALUES (1, 'testuser', 'dummy_hash', 'dummy_salt', 'user')"
    )
    conn.commit()
    conn.close()

    import pilotstd.core.config.paths as _paths

    _orig = _paths.get_db_path
    _paths.get_db_path = lambda: db_path

    router = _reload_admin_db()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.post("/query", json={"sql": "SELECT * FROM users WHERE id = ? LIMIT 10", "params": [1]})
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    _paths.get_db_path = _orig


@patch("docker.auth.require_role", lambda role: lambda f: f)
def test_api_delete_no_where_rejected(tmp_path):
    db_path = str(tmp_path / "api_del.db")
    import pilotstd.core.config.paths as _paths

    _orig = _paths.get_db_path
    _paths.get_db_path = lambda: db_path

    router = _reload_admin_db()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.post("/query", json={"sql": "DELETE FROM users"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION_FAILED"
    _paths.get_db_path = _orig


@patch("docker.auth.require_role", lambda role: lambda f: f)
def test_api_drop_database_rejected(tmp_path):
    db_path = str(tmp_path / "api_drop_db.db")
    import pilotstd.core.config.paths as _paths

    _orig = _paths.get_db_path
    _paths.get_db_path = lambda: db_path

    router = _reload_admin_db()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.post("/query", json={"sql": "DROP DATABASE test", "confirm_dangerous": True})
    assert resp.status_code == 400
    _paths.get_db_path = _orig
