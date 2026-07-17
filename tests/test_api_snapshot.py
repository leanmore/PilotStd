# tests/test_api_snapshot.py — API 响应结构快照测试
"""关键 API 端点的响应结构验证。

用 TestClient + 真实 SQLite 数据库（迁移链生成 Schema），
验证核心端点返回 200 且 JSON 包含预期顶层字段。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET", "snapshot_test_secret_key")
os.environ.setdefault("ADMIN_PASSWORD", "snapshot_test_pass_42")
os.environ.setdefault("SUPERUSER", "snapshot_admin")

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.auth import COOKIE_NAME, AuthMiddleware, get_current_username, require_admin
from docker.auth import router as auth_router
from docker.manager import get_manager_dep


@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    """创建 TestClient + 真实 Database fixture。"""
    tmpdir = tmp_path_factory.mktemp("snapshot")
    db_path = str(tmpdir / "test.db")

    from pilotstd.core.db import Database

    db = Database(db_path)

    # 插入公告测试数据
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name,"
        "  publish_date, fetched_at, announcement_title, standard_count)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "announcement_gb",
            "pid-snapshot-001",
            "2026年第15号",
            "GB/T 19001-2026",
            "质量管理体系要求",
            "2026-05-15",
            "2026-05-16",
            "2026年第15号公告",
            42,
        ),
    )
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name,"
        "  publish_date, fetched_at, announcement_title, standard_count)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "announcement_gb",
            "pid-snapshot-002",
            "2026年第15号",
            "GB/T 24001-2026",
            "环境管理体系要求",
            "2026-05-15",
            "2026-05-16",
            "2026年第15号公告",
            42,
        ),
    )

    # 直接创建 users 表和超级用户（避免 init_users_table 的副作用）
    db.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " username TEXT NOT NULL UNIQUE,"
        " password_hash TEXT NOT NULL,"
        " salt TEXT NOT NULL,"
        " role TEXT NOT NULL DEFAULT 'user',"
        " must_change_password INTEGER NOT NULL DEFAULT 0,"
        " created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))"
    )
    db.execute("CREATE TABLE IF NOT EXISTS login_attempts ( ip TEXT NOT NULL, attempt_time REAL NOT NULL)")
    from pilotstd.core.security import generate_salt, get_password_hash

    pwd = os.environ["ADMIN_PASSWORD"]
    pw_hash = get_password_hash(pwd)
    salt = generate_salt()
    db.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, salt, role, must_change_password)"
        " VALUES (?, ?, ?, ?, ?)",
        (os.environ["SUPERUSER"], pw_hash, salt, "admin", 0),
    )
    # 注入测试数据库到 users/auth 模块
    from docker import auth as auth_mod
    from docker import users as users_mod

    users_mod._db_instance = db
    auth_mod._init_done = True  # 跳过 init_users_table，使用上面手动创建的用户

    # 构造 mock manager
    mock_mgr = MagicMock()
    mock_mgr.db = db
    mock_mgr.file_index = MagicMock()
    mock_mgr.file_index.get_status_stats.return_value = {
        "current": 0,
        "expired": 0,
        "pending": 0,
        "upcoming": 0,
    }
    mock_mgr.announce_service = MagicMock()
    mock_mgr.announce_service.get_announcement_sources.return_value = []
    mock_mgr.pipeline_store = MagicMock()
    mock_mgr.query_by_numbers.return_value = ([], MagicMock())

    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    app.include_router(auth_router)
    from docker.api.announce import router as announce_router
    from docker.api.announce_detail import router as announce_detail_router
    from docker.api.query import router as query_router
    from docker.api.stats import router as stats_router

    app.include_router(announce_router)
    app.include_router(announce_detail_router)
    app.include_router(stats_router)
    app.include_router(query_router)

    app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
    app.dependency_overrides[get_current_username] = lambda: "snapshot_admin"
    app.dependency_overrides[require_admin] = lambda: "snapshot_admin"

    client = TestClient(app)
    yield client, db
    db.close()


@pytest.fixture
def auth_cookies(client_and_db):
    """登录并返回 cookies。"""
    client, _ = client_and_db
    r = client.post(
        "/api/login",
        data={"username": "snapshot_admin", "password": os.environ["ADMIN_PASSWORD"]},
    )
    return dict(r.cookies)


# ════════════════════════════════════════════════════════════════
# POST /api/login
# ════════════════════════════════════════════════════════════════


class TestLogin:
    def test_returns_200_and_ok(self, client_and_db):
        client, _ = client_and_db
        r = client.post(
            "/api/login",
            data={"username": "snapshot_admin", "password": os.environ["ADMIN_PASSWORD"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok")
        assert data.get("username") == "snapshot_admin"
        assert "role" in data
        assert COOKIE_NAME in r.cookies

    def test_wrong_password_returns_401(self, client_and_db):
        client, _ = client_and_db
        r = client.post(
            "/api/login",
            data={"username": "snapshot_admin", "password": "wrong_password"},
        )
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════
# GET /api/stats
# ════════════════════════════════════════════════════════════════


def test_stats_returns_200_and_fields(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    for field in ("current", "expired", "pending"):
        assert field in data, f"stats 响应缺少字段: {field}"


# ════════════════════════════════════════════════════════════════
# GET /api/announce/stats
# ════════════════════════════════════════════════════════════════


def test_announce_stats_returns_200_and_fields(client_and_db, auth_cookies):
    client, _ = client_and_db
    r = client.get("/api/announce/stats", cookies=auth_cookies)
    assert r.status_code == 200
    data = r.json()
    for field in ("total", "matched", "new"):
        assert field in data, f"announce/stats 响应缺少字段: {field}"


# ════════════════════════════════════════════════════════════════
# GET /api/announce/results
# ════════════════════════════════════════════════════════════════


def test_announce_results_returns_200_and_results(client_and_db, auth_cookies):
    client, _ = client_and_db
    r = client.get("/api/announce/results", cookies=auth_cookies)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert isinstance(data["results"], list)


# ════════════════════════════════════════════════════════════════
# GET /api/announcements/{announce_no}
# ════════════════════════════════════════════════════════════════


def test_announcement_detail_returns_200_and_structure(client_and_db, auth_cookies):
    client, _ = client_and_db
    r = client.get("/api/announcements/2026年第15号", cookies=auth_cookies)
    assert r.status_code == 200, f"公告详情应返回 200，实际 {r.status_code}"
    data = r.json()
    assert "announcement" in data
    assert "records" in data
    assert "parse_status" in data
    assert data["announcement"]["announce_no"] == "2026年第15号"
    assert isinstance(data["records"], list)
    assert len(data["records"]) >= 1


def test_announcement_detail_unknown_returns_404(client_and_db, auth_cookies):
    client, _ = client_and_db
    r = client.get("/api/announcements/9999年第99号", cookies=auth_cookies)
    assert r.status_code == 404


# ════════════════════════════════════════════════════════════════
# POST /api/query
# ════════════════════════════════════════════════════════════════


def test_query_empty_numbers_does_not_500(client_and_db, auth_cookies):
    client, _ = client_and_db
    csrf_token = auth_cookies.get("csrf_token", "")
    r = client.post(
        "/api/query",
        json={"numbers": [], "run_id": "snapshot-test-run"},
        cookies=auth_cookies,
        headers={"X-CSRF-Token": csrf_token} if csrf_token else {},
    )
    assert r.status_code in (200, 422), f"查询不应 500，实际 {r.status_code}: {r.text[:200]}"
