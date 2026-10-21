"""API 层：GET /api/announce/reconcile（Mock manager + 真实临时 DB）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api import announce
from docker.manager import get_manager_dep


@pytest.fixture()
def db(tmp_path):
    from pilotstd.core.db import Database

    database = Database(str(tmp_path / "reconcile.db"))
    yield database
    database.close()


@pytest.fixture()
def client(db) -> TestClient:
    mgr = MagicMock()
    mgr.db = db
    app = FastAPI()
    app.include_router(announce.router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    return TestClient(app)


def _insert(db, code: str, number: str, declared: int) -> None:
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name, publish_date,"
        "  fetched_at, matched, standard_count)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("announcement_hb", f"pid-{code}-{number}", code, number, "n", "2026-10-01", "2026-10-01", 1, declared),
    )


def test_reconcile_returns_declared_actual_diff(client: TestClient, db) -> None:
    _insert(db, "2026年第9号", "NB/SH/T 0001-2026", 3)
    _insert(db, "2026年第9号", "NB/SH/T 0002-2026", 3)
    _insert(db, "2026年第7号", "SJ/T 1-2026", 1)

    resp = client.get("/api/announce/reconcile")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["announce_no"] == "2026年第9号"
    assert (item["declared"], item["actual"], item["diff"]) == (3, 2, -1)


def test_reconcile_empty(client: TestClient) -> None:
    resp = client.get("/api/announce/reconcile")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}
