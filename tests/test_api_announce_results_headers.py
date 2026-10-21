"""公告列表：有公告头但零记录时也必须显示，避免漏抓公告从列表消失。"""

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

    database = Database(str(tmp_path / "announce_results.db"))
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


def _header(db, code: str) -> None:
    db.execute(
        "INSERT INTO announcements"
        " (source_site, pid, announce_no, title, publish_date, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("announcement_gb", f"pid-{code}", code, "零记录公告", "2025-06-01", "2025-06-01", "2025-06-01"),
    )


def _record(db, code: str) -> None:
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name, publish_date, fetched_at, standard_count)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("announcement_gb", f"pid-{code}", code, "GB 1-2020", "标准", "2025-06-02", "2025-06-02", 1),
    )


def test_header_without_records_is_listed(client: TestClient, db) -> None:
    _header(db, "2025年第99号")
    _record(db, "2025年第100号")

    resp = client.get("/api/announce/results")

    assert resp.status_code == 200
    codes = {x["announce_no"] for x in resp.json()["results"]}
    assert codes == {"2025年第99号", "2025年第100号"}
