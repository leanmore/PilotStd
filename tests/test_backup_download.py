"""C-4：备份下载端点（admin-only + 路径穿透防护）。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.backup import router as backup_router
from docker.manager import get_manager_dep
from tests._auth_helpers import admin_cookies, user_cookies


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "pilotstd.db"
    db_path.write_bytes(b"")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "ok.bak").write_bytes(b"SQLite format 3\x00")
    (backup_dir / "secret.txt").write_text("x")

    mgr = SimpleNamespace(db=SimpleNamespace(path=str(db_path)))
    app = FastAPI()
    app.include_router(backup_router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    return TestClient(app, cookies=admin_cookies())


def test_admin_can_download(client) -> None:
    r = client.get("/api/backup/download/ok.bak")
    assert r.status_code == 200
    assert r.content.startswith(b"SQLite format 3")


@pytest.mark.parametrize("name", ["../pilotstd.db", "..%2Fpilotstd.db", "a/b.bak", "secret.txt", "nope.bak"])
def test_rejects_traversal_and_missing(client, name) -> None:
    r = client.get(f"/api/backup/download/{name}")
    assert r.status_code in (400, 404)


def test_normal_user_forbidden(tmp_path) -> None:
    db_path = tmp_path / "pilotstd.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "ok.bak").write_bytes(b"x")
    mgr = SimpleNamespace(db=SimpleNamespace(path=str(db_path)))
    app = FastAPI()
    app.include_router(backup_router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    c = TestClient(app, cookies=user_cookies())
    r = c.get("/api/backup/download/ok.bak")
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"
