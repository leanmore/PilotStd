# tests/test_api_favorites_auth.py — 收藏接口鉴权回归测试（FIX-401 后端侧）
"""收藏接口 401 回归验证。

背景：/api/favorites/batch-status 等 5 个收藏接口此前返回 401"用户不存在"，
根因是 _get_user_id 用 get_current_user_id 返回的 user_id 去查询 username 列。
本测试用真实 AuthMiddleware + 真实 login 获取 Cookie，验证修复后接口返回 200。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.auth import COOKIE_NAME, AuthMiddleware
from docker.auth import router as auth_router

_TEST_USER = "favorites_admin"


@pytest.fixture(scope="module", autouse=True)
def _set_test_env():
    """设置测试环境变量，模块结束后恢复原值，避免污染其他测试文件。"""
    keys = ("JWT_SECRET", "ADMIN_PASSWORD", "SUPERUSER")
    old = {k: os.environ.get(k) for k in keys}
    os.environ["JWT_SECRET"] = "favorites_test_secret_key"
    os.environ["ADMIN_PASSWORD"] = "favorites_test_pass_42"
    os.environ["SUPERUSER"] = _TEST_USER
    yield
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    """创建 TestClient + 真实 SQLite 数据库 + 测试用户。"""

    tmpdir = tmp_path_factory.mktemp("favorites_fix")
    db_path = str(tmpdir / "test.db")

    from pilotstd.core.db import Database

    db = Database(db_path)

    # ── 用户表（id 自增，确保首个用户 id=1，与 JWT sub 一致）──
    db.execute(
        """CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);"""
    )
    db.execute("CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT NOT NULL, attempt_time REAL NOT NULL)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS user_favorites ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "user_id INTEGER NOT NULL,"
        "record_id INTEGER NOT NULL,"
        "status TEXT DEFAULT 'pending',"
        "local_path TEXT,"
        "error_message TEXT,"
        "publish_date TEXT,"
        "last_archive_attempt TEXT,"
        "archive_retry_count INTEGER DEFAULT 0,"
        "standard_number TEXT,"
        "standard_type TEXT NOT NULL DEFAULT 'Unknown',"
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP,"
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    # 迁移框架可能已用 v31 旧结构建表（无 standard_number/standard_type），此处幂等补列
    _uf_cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")}
    if "standard_type" not in _uf_cols:
        db.execute("ALTER TABLE user_favorites ADD COLUMN standard_type TEXT NOT NULL DEFAULT 'Unknown'")
    if "standard_number" not in _uf_cols:
        db.execute("ALTER TABLE user_favorites ADD COLUMN standard_number TEXT")
    db.execute(
        """CREATE TABLE IF NOT EXISTS announcement_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_site TEXT NOT NULL,
        pid TEXT NOT NULL,
        announce_no TEXT,
        standard_number TEXT NOT NULL,
        std_name TEXT,
        publish_date TEXT,
        fetched_at TEXT NOT NULL,
        matched INTEGER DEFAULT 0,
        source_version TEXT DEFAULT 'initial',
        data_state TEXT DEFAULT 'fresh',
        last_accessed_at TEXT,
        announcement_title TEXT,
        standard_count INTEGER,
        announcement_id INTEGER,
        row_index INTEGER,
        implement_date TEXT,
        expiry_date TEXT,
        superseded_by TEXT,
        status TEXT DEFAULT 'draft',
        confidence REAL DEFAULT 0.0,
        raw_text TEXT,
        parser_engine TEXT,
        approved_by INTEGER,
        approved_at TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        source_type TEXT DEFAULT '网页解析',
        standard_type TEXT NOT NULL DEFAULT 'Unknown',
        UNIQUE(source_site, pid, standard_number))"""
    )

    from pilotstd.core.security import generate_salt, get_password_hash

    pw_hash = get_password_hash(os.environ["ADMIN_PASSWORD"])
    salt = generate_salt()
    db.execute(
        "INSERT INTO users (username, password_hash, salt, role, must_change_password)"
        " VALUES (?, ?, ?, ?, ?)",
        (_TEST_USER, pw_hash, salt, "admin", 0),
    )

    # 注入测试数据库到 users/auth 模块，确保 login 端点使用测试 DB
    from docker import auth as auth_mod
    from docker import users as users_mod

    users_mod._db_instance = db
    auth_mod._init_done = True

    # ── 构建 app：AuthMiddleware 真实执行，仅 override favorites 的 get_db ──
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(auth_router)

    from docker.api.favorites import get_db
    from docker.api.favorites import router as favorites_router

    app.include_router(favorites_router)
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    yield client, db
    db.close()


@pytest.fixture(scope="module")
def auth_cookies(client_and_db):
    """模块级：真实登录获取 cookie，所有测试共享。"""
    client, _ = client_and_db
    r = client.post(
        "/api/login",
        data={"username": _TEST_USER, "password": os.environ["ADMIN_PASSWORD"]},
    )
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text[:200]}"
    cookies = dict(r.cookies)
    assert COOKIE_NAME in cookies, "登录响应未包含 pilotstd_token cookie"
    return cookies


def test_batch_status_returns_200(client_and_db, auth_cookies):
    """回归：带 Cookie 的批量状态查询不再返回 401。"""
    client, _ = client_and_db
    r = client.post(
        "/api/favorites/batch-status",
        json={"record_ids": [1, 2]},
        headers={"X-CSRF-Token": auth_cookies["csrf_token"]},
    )
    assert r.status_code == 200, f"batch-status 应返回 200，实际 {r.status_code}: {r.text}"
    assert r.json() == {"statuses": {"1": None, "2": None}}


def test_add_favorite_returns_200(client_and_db, auth_cookies):
    """回归：带 Cookie 的收藏操作不再返回 401。"""
    client, db = client_and_db
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, announce_no, standard_number,"
        " std_name, publish_date, fetched_at, announcement_title, standard_count)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("announcement_gb", "pid-fav-001", "2026年第40号", "GB/T 40001-2026",
         "收藏回归测试标准", "2026-08-20", "2026-08-20", "2026年第40号公告", 1),
    )
    r = client.post(
        "/api/favorites",
        json={"record_id": 1},
        headers={"X-CSRF-Token": auth_cookies["csrf_token"]},
    )
    assert r.status_code == 200, f"收藏应返回 200，实际 {r.status_code}: {r.text}"
    assert r.json()["status"] == "pending"


def test_list_favorites_returns_200(client_and_db):
    """回归：带 Cookie 的收藏列表不再返回 401。"""
    client, _ = client_and_db
    r = client.get("/api/favorites")
    assert r.status_code == 200, f"收藏列表应返回 200，实际 {r.status_code}: {r.text}"
    assert "favorites" in r.json()


def test_favorites_401_without_cookie(client_and_db):
    """无 Cookie 时中间件仍返回 401（鉴权链路未被绕过）。"""
    client, _ = client_and_db
    client.cookies.clear()  # 清空 TestClient 自动持久化的登录 Cookie
    r = client.post("/api/favorites/batch-status", json={"record_ids": [1]})
    assert r.status_code == 401
